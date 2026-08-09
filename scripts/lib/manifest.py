"""
Manifest data model for the weekly-update orchestrator.

A run has two snapshots (pre, post) plus a diff. Each snapshot is a list of
Component records, where a Component carries everything we need to know about
one tool or package in order to upgrade it AND verify the upgrade.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class Component:
    """One tracked tool / package."""

    name: str                              # e.g. "hermes", "codex", "rustc"
    category: str                          # "agent" | "runtime" | "package_manager" | "skill_source" | "tool"
    version_before: Optional[str] = None   # string as reported by `tool --version`
    version_after: Optional[str] = None
    upgrade_cmd: str = ""                  # exact command string we ran (or "" for skipped)
    skip_reason: Optional[str] = None      # non-None if deliberately skipped this run
    failure: Optional[str] = None         # error message if this step failed
    warning: Optional[str] = None         # non-fatal issue (e.g. backup snapshot failed); surfaced in digest
    duration_s: float = 0.0
    bin_path: Optional[str] = None         # path returned by `which`


@dataclass
class Snapshot:
    """One full machine state at a point in time."""

    captured_at: str                       # ISO-8601 UTC
    components: list[Component] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "Snapshot":
        data = json.loads(text)
        return cls(
            captured_at=data["captured_at"],
            components=[Component(**c) for c in data["components"]],
        )


def _which(name: str) -> Optional[str]:
    try:
        return subprocess.check_output(["which", name], text=True, timeout=5).strip() or None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def _version_of(name: str, args: tuple[str, ...] = ("--version",)) -> Optional[str]:
    binp = _which(name)
    if not binp:
        return None
    try:
        out = subprocess.check_output([binp, *args], text=True, timeout=10, stderr=subprocess.STDOUT)
        return out.strip().splitlines()[0] if out.strip() else None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


# Components the orchestrator tracks. The recon report on 2026-08-09 found these;
# keep this list in sync with `which`/`--version` results.
TRACKED: list[dict] = [
    # category "agent"
    {"name": "hermes",   "category": "agent", "version_args": ("--version",)},
    {"name": "codex",    "category": "agent", "version_args": ("--version",)},
    {"name": "claude",   "category": "agent", "version_args": ("--version",)},
    {"name": "opencode", "category": "agent", "version_args": ("--version",)},
    {"name": "openclaw", "category": "agent", "version_args": ("--version",)},
    {"name": "pi",       "category": "agent", "version_args": ("--version",)},
    # category "runtime"
    {"name": "rustc",    "category": "runtime", "version_args": ("--version",)},
    {"name": "bun",      "category": "runtime", "version_args": ("--version",)},
    {"name": "node",     "category": "runtime", "version_args": ("--version",)},
    # category "package_manager"
    {"name": "npm",      "category": "package_manager", "version_args": ("--version",)},
    {"name": "bunx",     "category": "package_manager", "version_args": ("--version",)},
    {"name": "uv",       "category": "package_manager", "version_args": ("--version",)},
    {"name": "rustup",   "category": "package_manager", "version_args": ("--version",)},
    # category "tool"
    {"name": "gh",       "category": "tool", "version_args": ("--version",)},
    {"name": "fish",     "category": "tool", "version_args": ("--version",)},
    {"name": "atuin",    "category": "tool", "version_args": ("--version",)},
    {"name": "vim",      "category": "tool", "version_args": ("--version",)},
    {"name": "ctx7",     "category": "tool", "version_args": ("--version",)},
    {"name": "codegraph","category": "tool", "version_args": ("--version",)},
    # category "skill_source"
    {"name": "/root/.agents/skills/", "category": "skill_source", "version_args": ()},
    # category "skill_categories" — non-symlink subdir names of ~/.hermes/skills/
    # representing the hermes-bundled category set synced by `hermes update`.
    # version string is a comma-separated sorted list of names (stable, diffable).
    # See ADR 0005.
    {"name": "category_dirs", "category": "skill_categories", "version_args": ()},
]


def _hermes_skill_category_set(hermes_home: str = "/root/.hermes") -> Optional[str]:
    """Return a stable string describing the bundled-skill category names that
    Hermes has currently synced into `~/.hermes/skills/`.

    We treat any entry — real directory OR symlink — as "synced". A symlink
    at `~/.hermes/skills/<name>` typically points at
    `/root/.agents/skills/<name>`; that means the user has manually taken
    over this category, and Hermes correctly defers to the symlink rather
    than clobbering it. So both states count as present for sync-tracking
    purposes. Hidden dotfiles are excluded.

    The resulting string is comma-joined sorted names — stable, diffable,
    and short enough to live in a manifest `version` field.
    """
    skills_root = Path(hermes_home) / "skills"
    if not skills_root.is_dir():
        return None
    names: list[str] = []
    for entry in sorted(skills_root.iterdir()):
        if entry.name.startswith("."):
            continue
        # entry.is_dir() follows symlinks, so a live symlink to a real
        # directory counts; a dangling symlink does not. We accept either
        # followable directory or any symlink to be permissive.
        if entry.is_dir() or entry.is_symlink():
            names.append(entry.name)
    return ",".join(names) if names else None


def capture() -> Snapshot:
    """Snapshot every tracked component's current state."""
    snap = Snapshot(captured_at=datetime.now(timezone.utc).isoformat())
    for spec in TRACKED:
        name = spec["name"]
        args = spec.get("version_args") or ("--version",)
        if name.endswith("/"):
            # skill source: read git HEAD short sha
            version = _git_head(name)
            binp = name
        elif name == "category_dirs":
            # ADR 0005: tracked snapshot of hermes-bundled category names.
            version = _hermes_skill_category_set()
            binp = str(Path.home() / ".hermes" / "skills")
        else:
            version = _version_of(name, args)
            binp = _which(name)
        snap.components.append(Component(
            name=name,
            category=spec["category"],
            version_before=version,
            bin_path=binp,
        ))
    return snap


def _git_head(path: str) -> Optional[str]:
    try:
        return subprocess.check_output(
            ["git", "-C", path, "rev-parse", "--short", "HEAD"],
            text=True, timeout=5,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def write_snapshot(snap: Snapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snap.to_json())


def diff(pre: Snapshot, post: Snapshot) -> dict:
    """Return a dict describing what changed between two snapshots."""
    pre_map = {c.name: c for c in pre.components}
    post_map = {c.name: c for c in post.components}
    out = {"upgraded": [], "unchanged": [], "newly_installed": [], "removed": []}
    for name, post_c in post_map.items():
        pre_c = pre_map.get(name)
        if pre_c is None:
            out["newly_installed"].append({"name": name, "version": post_c.version_after})
            continue
        if pre_c.version_before != post_c.version_after:
            out["upgraded"].append({
                "name": name,
                "before": pre_c.version_before,
                "after": post_c.version_after,
            })
        else:
            out["unchanged"].append({"name": name, "version": post_c.version_after})
    for name in pre_map:
        if name not in post_map:
            out["removed"].append({"name": name})
    return out


def prune_old_runs(base: Path, keep: int = 8) -> None:
    """Delete run directories older than the `keep` most recent."""
    if not base.exists():
        return
    runs = sorted(p for p in base.iterdir() if p.is_dir())
    for old in runs[:-keep]:
        import shutil
        shutil.rmtree(old, ignore_errors=True)