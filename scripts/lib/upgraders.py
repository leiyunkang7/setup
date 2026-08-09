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

def _prune_old_backups(base: Path, keep: int) -> int:
    """Delete all but the `keep` most-recently-named entries under `base`.
    Returns the number of entries removed. Naming is timestamp-based so a
    sorted() on name gives chronological order — no need to stat mtimes.
    """
    if not base.exists():
        return 0
    entries = sorted(p for p in base.iterdir()
                     if p.is_dir() or p.name.endswith(".tar.gz"))
    # Skip the freshest `keep` entries (named with the latest timestamps).
    for old in entries[:-keep] if keep > 0 else entries:
        if old.is_dir():
            import shutil as _sh
            _sh.rmtree(old, ignore_errors=True)
        else:
            try:
                old.unlink()
            except FileNotFoundError:
                pass
    return max(0, len(entries) - keep)


def upgrade_hermes(c: Component, *, dry_run: bool) -> Component:
    """Run hermes's own upgrade command. Pre-flight backup per ADR 0002.

    Backup contents at ~/.hermes/backups/pre-hermes-upgrade-<ts>/:
      - tarball: hermes-agent.tar.gz  (full /usr/local/lib/hermes-agent snapshot)
      - patches.diff                  (small git diff of working-tree changes vs HEAD;
                                       this is what makes re-deriving the patches cheap
                                       per ADR 0002's "re-derive from backups" hint)
      - HEAD-pre.txt                  (git rev-parse HEAD before upgrade, for provenance)

    The patches are deliberately NOT reapplied after upgrade (ADR 0002: the cost
    of an unattended auto-reapply outweighs the value). Backup is best-effort;
    if either step fails, the upgrade still proceeds and a `warning` is attached
    so the digest surfaces it on Monday.
    """
    started = time.monotonic()
    cmd = ["hermes", "update"]
    if dry_run:
        return replace(c, version_after=c.version_before, upgrade_cmd=" ".join(cmd), duration_s=0.0)

    backup_base = Path.home() / ".hermes" / "backups"
    backup_dir = backup_base / f"pre-hermes-upgrade-{int(started)}"

    warnings: list[str] = []
    try:
        backup_base.mkdir(parents=True, exist_ok=True)
        backup_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        # If we can't even create the backup dirs (read-only home, full disk,
        # etc.), record the warning and skip the snapshot. The upgrade still
        # proceeds — ADR 0002 says backup is best-effort.
        warnings.append(f"backup dir creation failed: {e}")

    if not warnings:
        # Step 1: record HEAD + working-tree diff BEFORE upgrade. These two
        # files are tiny (<10KB even with all of cli.py) and are the artifact
        # that lets the user re-derive patches without untarring the snapshot.
        try:
            head_proc = subprocess.run(
                ["git", "-C", "/usr/local/lib/hermes-agent", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            (backup_dir / "HEAD-pre.txt").write_text(
                (head_proc.stdout if head_proc.returncode == 0 else f"<git failed: {head_proc.stderr.strip()}>").strip() + "\n"
            )
            diff_proc = subprocess.run(
                ["git", "-C", "/usr/local/lib/hermes-agent", "diff", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            diff_text = diff_proc.stdout if diff_proc.returncode == 0 else ""
            (backup_dir / "patches.diff").write_text(diff_text)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            warnings.append(f"git pre-snapshot failed: {e}")

        # Step 2: tarball snapshot. Best-effort — large but cheap. We exclude
        # .git so the snapshot is the *working tree* only; the patches.diff
        # above is what the user needs to reconstruct any uncommitted edits.
        try:
            tar_proc = subprocess.run(
                ["tar", "-czf", str(backup_dir / "hermes-agent.tar.gz"),
                 "--exclude=.git",
                 "-C", "/usr/local/lib", "hermes-agent"],
                capture_output=True, text=True, timeout=120,
            )
            if tar_proc.returncode != 0:
                warnings.append(f"tar snapshot failed (exit {tar_proc.returncode}): {tar_proc.stderr.strip()[:200]}")
        except subprocess.TimeoutExpired:
            warnings.append("tar snapshot timed out after 120s")
        except FileNotFoundError:
            warnings.append("tar binary not found on PATH")

        # Step 3: rotate. Keep last 4 backups (≈1 month of weekly runs).
        try:
            _prune_old_backups(backup_base, keep=4)
        except OSError as e:
            warnings.append(f"backup rotation failed: {e}")

    # Step 4: actual upgrade.
    code, out, err = _run(cmd, timeout=600)
    after = _read_version("hermes")
    return replace(
        c, version_after=after or c.version_before,
        upgrade_cmd=" ".join(cmd),
        failure=None if code == 0 else (err or out or f"exit {code}"),
        warning="; ".join(warnings) if warnings else None,
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