"""
Per-step upgrade functions for the weekly-update orchestrator.

Each function takes a `Component` (from manifest.py), runs the appropriate
upgrade command, returns the new Component with version_after / upgrade_cmd /
duration_s / failure filled in.

The convention: a function MUST NOT raise on upgrade failure. It captures
the error on the Component and returns. The orchestrator inspects the result
to decide whether to continue or abort (per Q24, abort on first failure,
leave already-successful steps in place).
"""
from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import replace
from pathlib import Path

from .manifest import Component


def _run(cmd: list[str], *, cwd: str | None = None, timeout: int = 300) -> tuple[int, str, str]:
    """Run `cmd`, return (exit_code, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd, cwd=cwd,
            capture_output=True, text=True, timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except FileNotFoundError as e:
        return 127, "", str(e)


def _read_version(bin_name: str, args: tuple[str, ...] = ("--version",)) -> str | None:
    binp = shutil.which(bin_name)
    if not binp:
        return None
    try:
        out = subprocess.check_output([binp, *args], text=True, timeout=10, stderr=subprocess.STDOUT)
        return out.strip().splitlines()[0] if out.strip() else None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


# --------- per-component upgraders ---------

def upgrade_hermes(c: Component, *, dry_run: bool) -> Component:
    """Run hermes's own upgrade command. Pre-flight tar to backup (per ADR 0002)."""
    started = time.monotonic()
    cmd = ["hermes", "update"]
    if dry_run:
        return replace(c, version_after=c.version_before, upgrade_cmd=" ".join(cmd), duration_s=0.0)
    backup_dir = Path.home() / ".hermes" / "backups" / f"pre-hermes-upgrade-{int(started)}"
    backup_dir.parent.mkdir(parents=True, exist_ok=True)
    # Per ADR 0002, we DO save a backup before upgrade, but we DO NOT reapply patches.
    # Backup is purely for forensic recovery if the user later regrets dropping patches.
    try:
        subprocess.run(
            ["tar", "-czf", str(backup_dir) + ".tar.gz",
             "-C", "/usr/local/lib", "hermes-agent"],
            check=False, timeout=60,
        )
    except Exception:
        pass  # backup is best-effort
    code, out, err = _run(cmd, timeout=600)
    after = _read_version("hermes")
    return replace(
        c, version_after=after or c.version_before,
        upgrade_cmd=" ".join(cmd),
        failure=None if code == 0 else (err or out or f"exit {code}"),
        duration_s=time.monotonic() - started,
    )


def upgrade_rustup(c: Component, *, dry_run: bool) -> Component:
    started = time.monotonic()
    cmd = ["rustup", "update"]
    if dry_run:
        return replace(c, version_after=c.version_before, upgrade_cmd=" ".join(cmd), duration_s=0.0)
    code, out, err = _run(cmd, timeout=600)
    after = _read_version("rustc")
    return replace(c, version_after=after or c.version_before, upgrade_cmd=" ".join(cmd),
                   failure=None if code == 0 else (err or out or f"exit {code}"),
                   duration_s=time.monotonic() - started)


def upgrade_npm_globals(c: Component, *, dry_run: bool, skip: set[str]) -> Component:
    """npm update -g for every top-level global package, minus skip list (Q21=C)."""
    started = time.monotonic()
    if dry_run:
        return replace(c, version_after=c.version_before, upgrade_cmd="npm update -g (dry-run)", duration_s=0.0)
    # List globals first, then upgrade each non-skipped one.
    code, listing, err = _run(["npm", "ls", "-g", "--depth=0"], timeout=60)
    pkgs: list[str] = []
    for line in listing.splitlines():
        line = line.strip()
        # lines look like "├── pkg@1.2.3" or "└── pkg@1.2.3"
        if "@" in line and not line.startswith("npm"):
            tail = line.lstrip("├└─").strip()
            name = tail.split("@", 1)[0]
            if name and name not in skip and not name.startswith("npm@"):
                pkgs.append(name)
    failures: list[str] = []
    for pkg in pkgs:
        rc, _, e = _run(["npm", "install", "-g", pkg], timeout=300)
        if rc != 0:
            failures.append(f"{pkg}: {e.strip()[:120]}")
    after = _read_version("npm")
    return replace(c, version_after=after or c.version_before,
                   upgrade_cmd=f"npm update -g ({len(pkgs)} pkgs)",
                   failure="; ".join(failures) if failures else None,
                   duration_s=time.monotonic() - started)


def upgrade_bun_globals(c: Component, *, dry_run: bool, skip: set[str]) -> Component:
    """bun add -g --latest for every bin in /root/.bun/install/global/node_modules/.bin/."""
    started = time.monotonic()
    bins_dir = Path("/root/.bun/install/global/node_modules/.bin")
    if dry_run or not bins_dir.is_dir():
        return replace(c, version_after=c.version_before, upgrade_cmd="bun add -g --latest (dry-run)", duration_s=0.0)
    bins = [p.name for p in bins_dir.iterdir() if not p.name.startswith(".")]
    bins = [b for b in bins if b not in skip]
    failures: list[str] = []
    for b in bins:
        rc, _, e = _run(["bun", "add", "-g", "--latest", b], timeout=300)
        if rc != 0:
            failures.append(f"{b}: {e.strip()[:120]}")
    after = _read_version("bun")
    return replace(c, version_after=after or c.version_before,
                   upgrade_cmd=f"bun add -g --latest ({len(bins)} bins)",
                   failure="; ".join(failures) if failures else None,
                   duration_s=time.monotonic() - started)


def upgrade_uv_tools(c: Component, *, dry_run: bool) -> Component:
    started = time.monotonic()
    cmd = ["uv", "tool", "upgrade", "--all"]
    if dry_run:
        return replace(c, version_after=c.version_before, upgrade_cmd=" ".join(cmd), duration_s=0.0)
    code, out, err = _run(cmd, timeout=300)
    after = _read_version("uv")
    return replace(c, version_after=after or c.version_before, upgrade_cmd=" ".join(cmd),
                   failure=None if code == 0 else (err or out or f"exit {code}"),
                   duration_s=time.monotonic() - started)


def upgrade_agent_npm(c: Component, *, dry_run: bool) -> Component:
    """Generic npm-installed agent: npm i -g <pkg-name>@latest."""
    started = time.monotonic()
    # Map of tracked agent → npm package name. Recon on 2026-08-09 found:
    # codex → @openai/codex, claude → @anthropic-ai/claude-code, openclaw → openclaw
    npm_pkg = {
        "codex": "@openai/codex",
        "claude": "@anthropic-ai/claude-code",
        "openclaw": "openclaw",
    }.get(c.name)
    if npm_pkg is None:
        return replace(c, skip_reason="no npm package mapping", duration_s=0.0)
    cmd = ["npm", "install", "-g", f"{npm_pkg}@latest"]
    if dry_run:
        return replace(c, version_after=c.version_before, upgrade_cmd=" ".join(cmd), duration_s=0.0)
    code, out, err = _run(cmd, timeout=300)
    after = _read_version(c.name)
    return replace(c, version_after=after or c.version_before, upgrade_cmd=" ".join(cmd),
                   failure=None if code == 0 else (err or out or f"exit {code}"),
                   duration_s=time.monotonic() - started)


def upgrade_opencode_bun(c: Component, *, dry_run: bool) -> Component:
    """opencode is bun-installed (opencode-ai)."""
    started = time.monotonic()
    cmd = ["bun", "add", "-g", "--latest", "opencode-ai"]
    if dry_run:
        return replace(c, version_after=c.version_before, upgrade_cmd=" ".join(cmd), duration_s=0.0)
    code, out, err = _run(cmd, timeout=300)
    after = _read_version("opencode")
    return replace(c, version_after=after or c.version_before, upgrade_cmd=" ".join(cmd),
                   failure=None if code == 0 else (err or out or f"exit {code}"),
                   duration_s=time.monotonic() - started)


def upgrade_pi_npm(c: Component, *, dry_run: bool) -> Component:
    """pi lives under hermes's bundled node — upgrade via the hermes node path."""
    started = time.monotonic()
    pi_pkg_dir = Path.home() / ".hermes/node/lib/node_modules/@earendil-works/pi-coding-agent"
    npm_with_hermes_node = Path.home() / ".hermes/node/bin/npm"
    if not npm_with_hermes_node.exists() or not pi_pkg_dir.exists():
        return replace(c, skip_reason="hermes node / pi pkg path missing", duration_s=0.0)
    cmd = [str(npm_with_hermes_node), "install", "-g", "@earendil-works/pi-coding-agent@latest"]
    if dry_run:
        return replace(c, version_after=c.version_before, upgrade_cmd=" ".join(cmd), duration_s=0.0)
    code, out, err = _run(cmd, timeout=300)
    after = _read_version("pi")
    return replace(c, version_after=after or c.version_before, upgrade_cmd=" ".join(cmd),
                   failure=None if code == 0 else (err or out or f"exit {code}"),
                   duration_s=time.monotonic() - started)


def upgrade_skills_repo(c: Component, *, dry_run: bool) -> Component:
    """git pull --rebase on /root/.agents/skills/ (the single source)."""
    started = time.monotonic()
    repo = Path("/root/.agents/skills/")
    if not (repo / ".git").exists():
        return replace(c, skip_reason="/root/.agents/skills/ is not a git repo",
                       duration_s=0.0)
    cmd = ["git", "-C", str(repo), "pull", "--rebase", "--autostash"]
    if dry_run:
        return replace(c, version_after=c.version_before, upgrade_cmd=" ".join(cmd), duration_s=0.0)
    code, out, err = _run(cmd, timeout=120)
    after_sha = _run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], timeout=5)[1].strip() or None
    return replace(c, version_after=after_sha or c.version_before, upgrade_cmd=" ".join(cmd),
                   failure=None if code == 0 else (err or out or f"exit {code}"),
                   duration_s=time.monotonic() - started)