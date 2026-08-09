#!/usr/bin/env python3
"""Regression test for the scrubbed environment used by Hermes cron."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import feishu  # pyright: ignore[reportMissingImports]

WEEKLY_UPDATE_SPEC = importlib.util.spec_from_file_location(
    "weekly_update", REPO_ROOT / "scripts" / "weekly-update.py"
)
assert WEEKLY_UPDATE_SPEC and WEEKLY_UPDATE_SPEC.loader
weekly_update = importlib.util.module_from_spec(WEEKLY_UPDATE_SPEC)
WEEKLY_UPDATE_SPEC.loader.exec_module(weekly_update)


class _Builder:
    def __init__(self, built: object, captured: dict[str, object]) -> None:
        self._built = built
        self._captured = captured

    def __getattr__(self, name: str):
        def setter(value: object) -> "_Builder":
            self._captured[name] = value
            return self

        return setter

    def build(self) -> object:
        return self._built


class _Response:
    code = 0
    msg = "success"
    data = types.SimpleNamespace(message_id="test-message-id")

    @staticmethod
    def success() -> bool:
        return True


class FeishuCronEnvironmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            import dotenv  # pyright: ignore[reportMissingImports]  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest(
                "requires the Hermes venv's python-dotenv"
            ) from exc

    def test_real_send_loads_profile_env_after_cron_scrubs_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as raw_home:
            hermes_home = Path(raw_home) / ".hermes"
            hermes_home.mkdir()
            (hermes_home / ".env").write_text(
                "FEISHU_APP_ID=test-app\n"
                "FEISHU_APP_SECRET=test-secret\n"
                "FEISHU_HOME_CHANNEL=test-channel\n"
                "UNRELATED_API_KEY=must-not-be-loaded\n"
            )
            payload_log = Path(raw_home) / "payload.json"
            captured: dict[str, object] = {}

            fake_client = types.SimpleNamespace(
                im=types.SimpleNamespace(
                    v1=types.SimpleNamespace(
                        message=types.SimpleNamespace(create=lambda _request: _Response())
                    )
                )
            )
            fake_lark = types.SimpleNamespace(
                FEISHU_DOMAIN="feishu-domain",
                LARK_DOMAIN="lark-domain",
                LogLevel=types.SimpleNamespace(WARNING="warning"),
                Client=types.SimpleNamespace(
                    builder=lambda: _Builder(fake_client, captured)
                ),
                im=types.SimpleNamespace(
                    v1=types.SimpleNamespace(
                        CreateMessageRequest=types.SimpleNamespace(
                            builder=lambda: _Builder(object(), {})
                        ),
                        CreateMessageRequestBody=types.SimpleNamespace(
                            builder=lambda: _Builder(object(), {})
                        ),
                    )
                ),
            )

            cron_env = {
                "HOME": raw_home,
                "HERMES_HOME": str(hermes_home),
                "PATH": os.environ.get("PATH", ""),
            }
            with patch.dict(os.environ, cron_env, clear=True), patch.dict(
                sys.modules, {"lark_oapi": fake_lark}
            ):
                feishu.send("cron digest", dry_run=False, payload_log=payload_log)
                self.assertNotIn("UNRELATED_API_KEY", os.environ)

            self.assertEqual("test-app", captured["app_id"])
            self.assertEqual("test-secret", captured["app_secret"])
            payload = json.loads(payload_log.read_text())
            self.assertEqual("test-channel", payload["channel"])
            self.assertEqual("test-message-id", payload["_response"]["message_id"])

    def test_empty_hermes_home_falls_back_to_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as raw_home:
            default_home = Path(raw_home) / ".hermes"
            default_home.mkdir()
            (default_home / ".env").write_text("FEISHU_APP_ID=default-app\n")

            with patch.dict(
                os.environ,
                {"HOME": raw_home, "HERMES_HOME": ""},
                clear=True,
            ):
                feishu._load_env_file()
                self.assertEqual("default-app", os.environ["FEISHU_APP_ID"])

    def test_env_loader_accepts_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as raw_home:
            hermes_home = Path(raw_home) / ".hermes"
            hermes_home.mkdir()
            (hermes_home / ".env").write_text(
                "\ufeffFEISHU_APP_ID=bom-app\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"HOME": raw_home, "HERMES_HOME": str(hermes_home)},
                clear=True,
            ):
                feishu._load_env_file()
                self.assertEqual("bom-app", os.environ["FEISHU_APP_ID"])


class WeeklyUpdateConfigTest(unittest.TestCase):
    def test_skip_file_supports_inline_comments(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            skip_file = Path(raw_dir) / "skip.txt"
            skip_file.write_text(
                "# full-line comment\n"
                "node # managed by fnm\n"
                "pip\n"
                "\n"
            )
            with patch.object(weekly_update, "SKIP_FILE", skip_file):
                self.assertEqual({"node", "pip"}, weekly_update._load_skip())


if __name__ == "__main__":
    unittest.main()
