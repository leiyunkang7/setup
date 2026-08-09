#!/usr/bin/env python3
# IMPORTANT: real runs must use /usr/local/lib/hermes-agent/venv/bin/python (not /usr/bin/python3)
# because the Feishu send path imports lark_oapi from Hermes's own venv.
# Cron registers weekly-update.sh via --no-agent --script; that wrapper selects
# the required interpreter before invoking this sibling script. See ADR 0004.
# Manual runs:
#     /usr/local/lib/hermes-agent/venv/bin/python /root/.hermes/scripts/weekly-update.py [--dry-run]
"""
weekly-update-all — orchestrator entry point.

Run sequence (per Q27):

  1. preflight + capture() (pre snapshot)
  2. run upgrade pipeline in order; on first failure, abort remaining steps
  3. capture() again (post snapshot)
  4. health gate on every upgraded tool
  5. write manifest (pre/post/diff/log/digest) under ~/.hermes/cache/weekly-update/<ts>/
  6. push digest to hermes-side feishu
  7. prune old runs (keep 8)

Usage:
  /root/.hermes/scripts/weekly-update.sh [--dry-run]

In dry-run, every upgrade step is skipped (records the command it WOULD run)
and the feishu push is replaced with a payload-log file. No network calls,
no installs, no reboots.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

# ensure we can import the lib/ package when invoked from cron
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import feishu, health, manifest, digest
from lib import upgraders as up


RUNS_BASE = Path.home() / ".hermes" / "cache" / "weekly-update"
SKIP_FILE = Path(__file__).resolve().parent / "skip.txt"


def _load_skip() -> set[str]:
    skip: set[str] = set()
    if SKIP_FILE.exists():
        for line in SKIP_FILE.read_text().splitlines():
            name = line.split("#", 1)[0].strip()
            if name:
                skip.add(name)
    return skip


def _new_run_dir(base: Path, ts: str) -> Path:
    """Return a unique run dir under `base` for a given UTC timestamp.

    The discriminator `pid-6hex` makes same-second re-runs safe: the overlap
    lock in the wrapper prevents live cron re-triggers from colliding, but a
    user manually re-running the script inside one second (or the cron
    delivery + a manual retry) would otherwise overwrite the prior run's
    pre.json / post.json / digest.md / feishu-payload.json.
    """
    return base / f"{ts}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


def _preflight() -> bool:
    import subprocess
    try:
        rc = subprocess.run(
            ["curl", "-s", "--max-time", "5", "-o", "/dev/null",
             "-w", "%{http_code}", "https://www.google.com"],
            capture_output=True, text=True, timeout=10,
        ).returncode
        if rc != 0:
            print("[preflight] network probe failed — mihomo / proxy may be down", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[preflight] probe raised {e}", file=sys.stderr)
        return False
    return True


def _run_pipeline(post_components: list[manifest.Component],
                  *, dry_run: bool, skip: set[str]) -> tuple[list[manifest.Component], bool]:
    """Execute the upgrade pipeline. Returns (updated_components, aborted)."""
    by_name = {c.name: c for c in post_components}
    aborted = False

    # Step ordering per Q27. Each entry: (name, fn-or-None).
    # The first item is the order; the second is the upgrade function (taking Component, **kwargs).
    pipeline: list[tuple[str, Callable[..., manifest.Component]]] = [
        ("hermes",         up.upgrade_hermes),         # first phase of the single cron; see ADR 0006
        ("category_dirs",  lambda c, dry_run: up.upgrade_skill_categories(   # ADR 0005 verify gate
            c, dry_run=dry_run,
            hermes_upgraded=by_name.get("hermes") is not None
                          and by_name["hermes"].version_after is not None
                          and by_name["hermes"].version_after != by_name["hermes"].version_before,
        )),
        ("rustc",          up.upgrade_rustup),
        ("codex",          up.upgrade_agent_npm),
        ("claude",         up.upgrade_agent_npm),
        ("openclaw",       up.upgrade_agent_npm),
        ("opencode",       up.upgrade_opencode_bun),
        ("pi",             up.upgrade_pi_npm),
        ("npm",            lambda c, dry_run: up.upgrade_npm_globals(c, dry_run=dry_run, skip=skip)),
        ("bun",            lambda c, dry_run: up.upgrade_bun_globals(c, dry_run=dry_run, skip=skip)),
        ("uv",             up.upgrade_uv_tools),
        ("/root/.agents/skills/", up.upgrade_skills_repo),
    ]

    for name, fn in pipeline:
        c = by_name.get(name)
        if c is None:
            continue
        if name in skip:
            by_name[name] = c.__class__(**{**c.__dict__, "skip_reason": "in skip.txt"})
            continue
        result = fn(c, dry_run=dry_run)
        by_name[name] = result
        if result.failure and not dry_run:
            print(f"[abort] step {name!r} failed: {result.failure}", file=sys.stderr)
            aborted = True
            break
    return list(by_name.values()), aborted


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="capture state, plan upgrades, write digest, but don't run any upgrade")
    args = p.parse_args(argv)
    dry = args.dry_run

    started = time.monotonic()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # P0: same-second collides between concurrent runs (overlap lock now
    # serialises the launcher, but manual re-runs inside a one-second window
    # can still land on the same ts; the digest + payload files would silently
    # overwrite. Delegate the discriminator to a small helper so the contract
    # is unit-testable without mocking half the orchestrator.
    run_dir = _new_run_dir(RUNS_BASE, ts)
    run_dir.mkdir(parents=True, exist_ok=True)
    skip = _load_skip()

    if not dry and not _preflight():
        print("[abort] preflight failed — bailing before any upgrade", file=sys.stderr)
        return 2

    # 1. pre snapshot
    pre = manifest.capture()
    manifest.write_snapshot(pre, run_dir / "pre.json")

    # 2. pipeline (operates on a copy of pre.components)
    post_components, aborted = _run_pipeline(list(pre.components), dry_run=dry, skip=skip)

    # 3. post snapshot (refresh version_after for items we did NOT upgrade)
    post = manifest.Snapshot(captured_at=datetime.now(timezone.utc).isoformat(),
                             components=post_components)
    manifest.write_snapshot(post, run_dir / "post.json")

    # 4. health gate (only if we actually upgraded something)
    if not dry and not aborted:
        for c in post.components:
            if c.version_after and c.version_after != c.version_before:
                ok, msg = health.probe(c.name)
                if not ok:
                    print(f"[health] {c.name}: {msg}", file=sys.stderr)
                    aborted = True
                    break

    # 5. digest
    md = digest.render(pre, post, duration_s=time.monotonic() - started, aborted=aborted, dry_run=dry)
    (run_dir / "digest.md").write_text(md)

    # 6. push to hermes-side feishu
    feishu.send(md, dry_run=dry, payload_log=run_dir / "feishu-payload.json")

    # 7. prune
    manifest.prune_old_runs(RUNS_BASE, keep=8)

    return 1 if aborted else 0


if __name__ == "__main__":
    raise SystemExit(main())