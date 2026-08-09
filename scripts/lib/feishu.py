"""
Feishu message delivery for the weekly-update orchestrator.

Routed through hermes-side feishu (FEISHU_* env vars + lark_oapi SDK), NOT through
OpenClaw's channels.feishu adapter. See ADR 0003.

Implementation note: lark_oapi is only installed inside hermes's own venv at
/usr/local/lib/hermes-agent/venv/lib/python3.11/site-packages/lark_oapi/. This
script therefore MUST run under /usr/local/lib/hermes-agent/venv/bin/python.
The hermes cron we register (weekly-update-all) sets its `command` to invoke
weekly-update.py under that interpreter.

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
                        f"{var} not set. Check ~/.hermes/.env has FEISHU_APP_ID, "
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
    """Best-effort load of ~/.hermes/.env if dotenv is available.

    Only sets vars that are not already present in os.environ (so the calling
    shell wins over the .env file). We try python-dotenv first, otherwise fall
    back to a minimal parser so we don't add a runtime dependency.
    """
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import dotenv_values  # type: ignore
        for k, v in dotenv_values(env_path).items():
            os.environ.setdefault(k, v or "")
        return
    except ImportError:
        pass
    # Minimal fallback: KEY=VALUE lines, skip blanks and # comments.
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def _stub_payload(markdown: str, cfg: FeishuConfig) -> dict:
    return {
        "channel": cfg.home_channel,
        "thread_id": cfg.home_thread_id or None,
        "msg_type": "text",
        "content": {"text": markdown},
        "_note": "real send uses lark_oapi.im.v1.CreateMessageRequest + msg_type=interactive for markdown rendering",
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
    cfg = FeishuConfig(require_all=not dry_run)
    payload = _stub_payload(markdown, cfg)

    if dry_run:
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

    # Make sure FEISHU_* are present even when caller didn't source ~/.hermes/.env.
    _load_env_file()
    cfg = FeishuConfig(require_all=True)

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