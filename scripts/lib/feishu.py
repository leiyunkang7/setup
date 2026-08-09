"""
Feishu message delivery for the weekly-update orchestrator.

Routed through hermes-side feishu (FEISHU_* env vars + lark_oapi SDK), NOT through
OpenClaw's channels.feishu adapter. See ADR 0003.

Implementation note: lark_oapi is only installed inside Hermes's own venv.
Real sends therefore MUST run under /usr/local/lib/hermes-agent/venv/bin/python.
The weekly-update-all cron registers weekly-update.sh via --no-agent --script;
that wrapper selects the venv interpreter before invoking weekly-update.py.

Reference: plugins/platforms/feishu/adapter.py:_standalone_send in hermes source.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional


class FeishuConfig:
    """Reads FEISHU_* env vars. Required vars raise; dry-run tolerates missing."""

    REQUIRED = ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_HOME_CHANNEL")

    def __init__(self, *, require_all: bool = True) -> None:
        # In dry-run we never actually call the SDK, so missing vars are OK
        # (they're recorded as "<unset>" for payload-log readability).
        for var in self.REQUIRED:
            val = os.environ.get(var)
            if not val:
                if require_all:
                    raise KeyError(
                        f"{var} not set. Check $HERMES_HOME/.env has FEISHU_APP_ID, "
                        f"FEISHU_APP_SECRET, FEISHU_HOME_CHANNEL."
                    )
                val = "<unset>"
        self.app_id: str = os.environ.get("FEISHU_APP_ID", "<unset>")
        self.app_secret: str = os.environ.get("FEISHU_APP_SECRET", "<unset>")
        self.home_channel: str = os.environ.get("FEISHU_HOME_CHANNEL", "<unset>")
        self.domain: str = os.environ.get("FEISHU_DOMAIN", "feishu")
        self.connection_mode: str = os.environ.get("FEISHU_CONNECTION_MODE", "websocket")
        self.home_thread_id: str = (
            os.environ.get("FEISHU_HOME_CHANNEL_THREAD_ID", "").strip()
        )


def _load_env_file() -> None:
    """Best-effort load of the active Hermes profile's .env file.

    Only loads FEISHU_* vars and only when they are not already present in
    os.environ (so the calling shell wins over the .env file). Real sends run
    inside Hermes's venv, where python-dotenv is a required dependency. Other
    credentials in .env must not enter this process.
    """
    configured_home = os.environ.get("HERMES_HOME", "").strip()
    hermes_home = (
        Path(configured_home).expanduser()
        if configured_home
        else Path.home() / ".hermes"
    )
    env_path = hermes_home / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import dotenv_values  # type: ignore
    except ImportError as exc:
        raise RuntimeError("python-dotenv missing from the Hermes venv") from exc
    for k, v in dotenv_values(env_path, encoding="utf-8-sig").items():
        if k.startswith("FEISHU_"):
            os.environ.setdefault(k, v or "")


def _stub_payload(markdown: str, cfg: FeishuConfig) -> dict:
    return {
        "channel": cfg.home_channel,
        "thread_id": cfg.home_thread_id or None,
        "msg_type": "text",
        "content": {"text": markdown},
        "_note": "real send uses lark_oapi.im.v1.CreateMessageRequest with msg_type=text",
    }


def _render_for_log(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def send(markdown: str, *, dry_run: bool = True, payload_log: Optional[Path] = None) -> None:
    """Post `markdown` to FEISHU_HOME_CHANNEL.

    If dry_run=True, write the payload to `payload_log` instead of sending.
    If dry_run=False, dispatch through lark_oapi SDK (mirrors what hermes's
    _standalone_send does, but without taking on hermes's plugin-runtime
    dependency — see ADR 0003 + recon notes).
    """
    if dry_run:
        cfg = FeishuConfig(require_all=False)
        payload = _stub_payload(markdown, cfg)
        if payload_log is not None:
            payload_log.parent.mkdir(parents=True, exist_ok=True)
            payload_log.write_text(_render_for_log(payload))
        return

    # ---- real send ----
    # lark_oapi is only present in hermes's venv. If we're somehow running under
    # system python, fail loudly instead of pretending.
    try:
        import lark_oapi as lark  # type: ignore
    except ImportError:
        sys.stderr.write(
            "FATAL: lark_oapi not importable. weekly-update.py must run under\n"
            "       /usr/local/lib/hermes-agent/venv/bin/python (not /usr/bin/python3).\n"
        )
        raise

    # Cron sanitizes messaging credentials from script subprocesses. Reload the
    # active profile's .env before validating config so unattended sends work.
    _load_env_file()
    cfg = FeishuConfig(require_all=True)
    payload = _stub_payload(markdown, cfg)

    # 1. build client
    domain = lark.FEISHU_DOMAIN if cfg.domain != "lark" else lark.LARK_DOMAIN
    client = (
        lark.Client.builder()
        .app_id(cfg.app_id)
        .app_secret(cfg.app_secret)
        .domain(domain)
        .log_level(lark.LogLevel.WARNING)
        .build()
    )

    # 2. compose message body. We send as `text` (markdown renders passably in
    # feishu/lark text), which keeps payload simple and avoids the interactive-
    # card schema. Thread binding: hermes model is "reply into thread" — but
    # FEISHU_HOME_CHANNEL_THREAD_ID is empty in this user's env, so we send to
    # the channel itself.
    body = json.dumps({"text": markdown}, ensure_ascii=False)
    req = (
        lark.im.v1.CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            lark.im.v1.CreateMessageRequestBody.builder()
            .receive_id(cfg.home_channel)
            .msg_type("text")
            .content(body)
            .build()
        )
        .build()
    )

    resp = client.im.v1.message.create(req)
    if not resp.success():
        raise RuntimeError(
            f"feishu send failed: code={resp.code} msg={resp.msg} "
            f"err={getattr(resp, 'error', None)}"
        )
    # success path — nothing to log unless caller asked
    if payload_log is not None:
        payload_log.parent.mkdir(parents=True, exist_ok=True)
        payload_log.write_text(_render_for_log({
            **payload,
            "_response": {
                "message_id": getattr(resp.data, "message_id", None),
                "code": resp.code,
                "msg": resp.msg,
            },
        }))