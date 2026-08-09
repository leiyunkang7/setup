#!/usr/bin/env python3
"""Smoke test for ADR 0003 hermes-side feishu delivery.

Runs a single real send via lark_oapi to FEISHU_HOME_CHANNEL and prints the
returned message_id. Exits non-zero if the send fails. Does NOT touch any
upgrade pipeline.

Must be run under hermes's venv interpreter:
    /usr/local/lib/hermes-agent/venv/bin/python scripts/smoke-test-feishu.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# make `lib` importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import feishu  # noqa: E402

HELLO = (
    "# ADR 0003 smoke test\n"
    "Sent via hermes-side lark_oapi client (NOT OpenClaw).\n"
    "If you can read this in FEISHU_HOME_CHANNEL, the weekly-update digest path works.\n"
)

payload_log = Path("/tmp/feishu-smoke-test.json")


def main() -> int:
    print("[smoke] feishu module:", feishu.__file__)
    print("[smoke] sending hello to FEISHU_HOME_CHANNEL...")
    try:
        feishu.send(HELLO, dry_run=False, payload_log=payload_log)
    except Exception as e:
        print(f"[smoke] FAIL: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if not payload_log.exists():
        print("[smoke] FAIL: send returned but payload_log not written", file=sys.stderr)
        return 1
    body = json.loads(payload_log.read_text())
    resp = body.get("_response", {})
    mid = resp.get("message_id")
    code = resp.get("code")
    msg = resp.get("msg")
    print(f"[smoke] code={code} msg={msg!r} message_id={mid!r}")
    if code != 0 or not mid:
        print("[smoke] FAIL: non-success response", file=sys.stderr)
        return 1
    print(f"[smoke] OK — message_id={mid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
