#!/usr/bin/env python3
"""Executable contracts for ADR 0006's single weekly update cron."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import manifest  # pyright: ignore[reportMissingImports]

WEEKLY_UPDATE_SPEC = importlib.util.spec_from_file_location(
    "weekly_update_adr0006", SCRIPTS_DIR / "weekly-update.py"
)
assert WEEKLY_UPDATE_SPEC and WEEKLY_UPDATE_SPEC.loader
weekly_update = importlib.util.module_from_spec(WEEKLY_UPDATE_SPEC)
WEEKLY_UPDATE_SPEC.loader.exec_module(weekly_update)

ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
JOB_BLOCK = re.compile(
    r"(?ms)^  (?P<id>[0-9a-f]+) \[(?P<state>[^]]+)]\n"
    r"(?P<body>.*?)(?=^  [0-9a-f]+ \[|\Z)"
)
RUNTIME_FILES = (
    "weekly-update.sh",
    "weekly-update.py",
    "skip.txt",
    "lib/__init__.py",
    "lib/digest.py",
    "lib/feishu.py",
    "lib/health.py",
    "lib/manifest.py",
    "lib/upgraders.py",
)


def _iter_runtime_files() -> tuple[str, ...]:
    """Discover every runtime file the cron job needs from the repo.

    Hard-coding the set drifted the moment a contributor added a new `lib/*.py`
    or a new skip-style sibling — the deployment-identity test stayed green
    while the cron would have crashed at runtime. Walk the tree instead, and
    exclude test-only / host-specific surfaces that never run inside the worker.
    """
    skip_files = {"smoke-test-feishu.py"}
    skip_dirs = {"__pycache__", "version-watch"}
    collected: list[str] = []
    for path in sorted(SCRIPTS_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(SCRIPTS_DIR).as_posix()
        parts = rel.split("/")
        if any(part in skip_dirs for part in parts):
            continue
        if path.name in skip_files:
            continue
        if path.suffix not in (".py", ".sh") and path.name != "skip.txt":
            continue
        collected.append(rel)
    return tuple(collected)


LEGACY_UPDATE_JOBS = (
    "weekly-version-watch",
    "weekly-hermes-self-update",
)


def _hermes_home() -> Path:
    configured = os.environ.get("HERMES_HOME", "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".hermes"


def _first_pipeline_name() -> str:
    """Source-grep the first component name in the orchestrator's hard-coded
    pipeline tuple. The mock-based test verifies the *behavior*; this asserts
    the *invariant* that `hermes` is the very first entry — a contributor who
    reorders the tuple breaks the ADR's hermes-first promise even though the
    test below would still pass.
    """
    import ast

    tree = ast.parse((SCRIPTS_DIR / "weekly-update.py").read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "_run_pipeline":
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(
                stmt.target, ast.Name
            ) or stmt.target.id != "pipeline":
                continue
            value = stmt.value
            if not isinstance(value, ast.List) or not value.elts:
                raise AssertionError("_run_pipeline.pipeline is not a non-empty list")
            first = value.elts[0]
            if not isinstance(first, ast.Tuple) or not first.elts:
                raise AssertionError("first pipeline entry is not a tuple")
            name = first.elts[0]
            if not isinstance(name, ast.Constant) or not isinstance(name.value, str):
                raise AssertionError("first pipeline entry's name is not a str literal")
            return name.value
    raise AssertionError("_run_pipeline.pipeline assignment not found")


class SingleWeeklyUpdateCronTest(unittest.TestCase):
    def test_cli_lists_exactly_one_active_update_cron(self) -> None:
        hermes = shutil.which("hermes")
        if hermes is None:
            self.fail("hermes CLI is required to verify cron state")
        proc = subprocess.run(
            [hermes, "cron", "list", "--all"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        output = ANSI_ESCAPE.sub("", proc.stdout)
        blocks = [match.groupdict() for match in JOB_BLOCK.finditer(output)]
        update_jobs = [
            block for block in blocks
            if re.search(
                r"(?m)^    Name:\s+weekly-(?:update|version|hermes-self-update)",
                block["body"],
            )
        ]
        update_blocks = [
            block for block in update_jobs
            if re.search(r"(?m)^    Name:\s+weekly-update-all\s*$", block["body"])
        ]
        self.assertEqual(
            1,
            len(update_blocks),
            f"expected one weekly-update-all job, got {len(update_blocks)}:\n{output}",
        )
        self.assertEqual(
            1,
            len(update_jobs),
            "expected weekly-update-all to be the only tool-update/version-watch cron:\n"
            + output,
        )
        job = update_blocks[0]
        self.assertEqual("active", job["state"])
        self.assertRegex(job["body"], r"(?m)^    Schedule:\s+0 20 \* \* 0\s*$")
        next_run_match = re.search(
            r"(?m)^    Next run:\s+(?P<timestamp>\S+)\s*$",
            job["body"],
        )
        self.assertIsNotNone(next_run_match, "cron output omitted the effective next run")
        next_run = datetime.fromisoformat(next_run_match.group("timestamp"))  # type: ignore[union-attr]
        self.assertEqual(timedelta(0), next_run.utcoffset())
        self.assertEqual(6, next_run.weekday(), "effective run must be Sunday in UTC")
        self.assertEqual((20, 0), (next_run.hour, next_run.minute))
        self.assertRegex(job["body"], r"(?m)^    Deliver:\s+local\s*$")
        self.assertRegex(job["body"], r"(?m)^    Script:\s+weekly-update\.sh\s*$")
        self.assertRegex(job["body"], r"(?m)^    Mode:\s+no-agent \(script stdout delivered directly\)\s*$")
        for legacy_name in LEGACY_UPDATE_JOBS:
            self.assertNotRegex(
                output,
                rf"(?m)^    Name:\s+{re.escape(legacy_name)}\s*$",
                f"legacy second update cron still exists: {legacy_name}",
            )

    def test_deployed_runtime_files_match_repository(self) -> None:
        deployed_scripts = _hermes_home() / "scripts"
        if not deployed_scripts.is_dir():
            self.skipTest(f"deployed scripts directory not present: {deployed_scripts}")
        drift: list[str] = []
        for relative in _iter_runtime_files():
            repo_file = SCRIPTS_DIR / relative
            deployed_file = deployed_scripts / relative
            if not deployed_file.is_file():
                drift.append(f"missing: {deployed_file}")
            elif repo_file.read_bytes() != deployed_file.read_bytes():
                drift.append(f"content differs: {relative}")
        self.assertEqual([], drift, "cron deployment drift:\n" + "\n".join(drift))

    def test_pipeline_first_entry_is_hermes(self) -> None:
        self.assertEqual(
            "hermes",
            _first_pipeline_name(),
            "ADR 0006 pins Hermes as the first pipeline entry; any reordering "
            "breaks the hermes-before-everything-else invariant.",
        )

    def test_run_dir_uses_per_invocations_discriminator(self) -> None:
        with tempfile.TemporaryDirectory() as raw_base:
            base = Path(raw_base)
            ts = "20260809T000000Z"
            names = {weekly_update._new_run_dir(base, ts).name for _ in range(5)}
        self.assertEqual(5, len(names), f"run dir discriminator collided: {names}")
        for name in names:
            self.assertTrue(name.startswith(ts + "-"), f"unexpected prefix: {name}")
            suffix = name[len(ts) + 1 :]
            self.assertRegex(
                suffix,
                r"^\d+-[0-9a-f]{6}$",
                f"run dir discriminator malformed: {name}",
            )

    def test_pipeline_runs_hermes_then_category_gate_before_other_steps(self) -> None:
        calls: list[str] = []

        def fake_upgrade(component: manifest.Component, *, dry_run: bool) -> manifest.Component:
            self.assertTrue(dry_run)
            calls.append(component.name)
            return replace(component, version_after=component.version_before)

        def fake_category_gate(
            component: manifest.Component,
            *,
            dry_run: bool,
            hermes_upgraded: bool,
        ) -> manifest.Component:
            self.assertTrue(dry_run)
            self.assertFalse(hermes_upgraded)
            calls.append(component.name)
            return replace(component, version_after=component.version_before)

        components = [
            manifest.Component(name="rustc", category="runtime", version_before="rustc-before"),
            manifest.Component(
                name="category_dirs",
                category="skill_categories",
                version_before="category-before",
            ),
            manifest.Component(name="hermes", category="agent", version_before="hermes-before"),
        ]
        with patch.object(weekly_update.up, "upgrade_hermes", fake_upgrade), patch.object(
            weekly_update.up, "upgrade_rustup", fake_upgrade
        ), patch.object(
            weekly_update.up,
            "upgrade_skill_categories",
            fake_category_gate,
        ):
            _, aborted = weekly_update._run_pipeline(
                components,
                dry_run=True,
                skip=set(),
            )

        self.assertFalse(aborted)
        self.assertEqual(["hermes", "category_dirs", "rustc"], calls)

    def test_pipeline_orders_all_twelve_steps(self) -> None:
        """ADR 0006 pins Hermes as the first step; the full ordering of the
        rest matters for digest narrative and failure-stop semantics. Scramble
        the input manifest and assert the runtime visit order matches the
        source's hard-coded pipeline.
        """
        all_components = [
            manifest.Component(name="codex", category="agent", version_before="v"),
            manifest.Component(name="claude", category="agent", version_before="v"),
            manifest.Component(name="openclaw", category="agent", version_before="v"),
            manifest.Component(name="opencode", category="agent", version_before="v"),
            manifest.Component(name="pi", category="agent", version_before="v"),
            manifest.Component(name="rustc", category="runtime", version_before="v"),
            manifest.Component(name="bun", category="runtime", version_before="v"),
            manifest.Component(name="npm", category="package_manager", version_before="v"),
            manifest.Component(name="uv", category="package_manager", version_before="v"),
            manifest.Component(
                name="/root/.agents/skills/", category="skill_source", version_before="v"
            ),
            manifest.Component(
                name="category_dirs", category="skill_categories", version_before="v"
            ),
            manifest.Component(name="hermes", category="agent", version_before="v"),
        ]
        # Reverse the input deliberately.
        scrambled = list(reversed(all_components))
        seen: list[str] = []

        def _spy(component, *, dry_run, **kwargs):
            self.assertTrue(dry_run)
            seen.append(component.name)
            return replace(component, version_after=component.version_before)

        def _spy_category(
            component, *, dry_run, hermes_upgraded, **kwargs
        ):
            self.assertTrue(dry_run)
            seen.append(component.name)
            return replace(component, version_after=component.version_before)

        with patch.object(weekly_update.up, "upgrade_hermes", _spy), \
             patch.object(weekly_update.up, "upgrade_rustup", _spy), \
             patch.object(weekly_update.up, "upgrade_agent_npm", _spy), \
             patch.object(weekly_update.up, "upgrade_opencode_bun", _spy), \
             patch.object(weekly_update.up, "upgrade_pi_npm", _spy), \
             patch.object(weekly_update.up, "upgrade_npm_globals", _spy), \
             patch.object(weekly_update.up, "upgrade_bun_globals", _spy), \
             patch.object(weekly_update.up, "upgrade_uv_tools", _spy), \
             patch.object(weekly_update.up, "upgrade_skills_repo", _spy), \
             patch.object(weekly_update.up, "upgrade_skill_categories", _spy_category):
            _, aborted = weekly_update._run_pipeline(
                scrambled, dry_run=True, skip=set()
            )

        self.assertFalse(aborted)
        # Hermes first, category_dirs immediately after, then the rest in the
        # source's hard-coded order. Scrambled input does not change visit order.
        self.assertEqual(
            [
                "hermes",
                "category_dirs",
                "rustc",
                "codex",
                "claude",
                "openclaw",
                "opencode",
                "pi",
                "npm",
                "bun",
                "uv",
                "/root/.agents/skills/",
            ],
            seen,
        )


if __name__ == "__main__":
    unittest.main()
