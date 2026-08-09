"""
Build the 8-section markdown digest (per Q23 = detailed version).

Header
✅ Successes
❌ Failures
⏭ Skips
⚠ Warnings
🔍 Review items
📊 Size delta
🔜 Next-week plan
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from .manifest import Component, Snapshot, diff as snap_diff


def _section(title: str, items: Iterable[str]) -> str:
    items = list(items)
    if not items:
        return f"## {title}\n_(none)_\n"
    body = "\n".join(f"- {x}" for x in items)
    return f"## {title}\n{body}\n"


def render(pre: Snapshot, post: Snapshot, *, duration_s: float, aborted: bool, dry_run: bool) -> str:
    upgraded, failed, skipped, warnings, review = [], [], [], [], []
    d = snap_diff(pre, post)
    # In dry-run, all components appear "upgraded" because pre.before != post.after
    # (post.after is None for components the pipeline didn't touch). Filter to
    # only those the pipeline actually planned to upgrade.
    if dry_run:
        upgraded_candidates = [c for c in post.components if c.upgrade_cmd]
    else:
        upgraded_candidates = [
            c for c in post.components
            if any(u["name"] == c.name for u in d["upgraded"])
        ]
    for c in upgraded_candidates:
        pre_c = next((p for p in pre.components if p.name == c.name), c)
        upgraded.append(f"`{c.name}` {pre_c.version_before} → {c.version_after or '(unchanged)'}")
    for c in post.components:
        if c.failure:
            failed.append(f"`{c.name}` — {c.failure[:240]}")
        if c.skip_reason:
            skipped.append(f"`{c.name}` — {c.skip_reason}")
        if c.warning:
            warnings.append(f"`{c.name}` — {c.warning[:240]}")
    size_lines = _size_delta(pre, post)
    next_week = _next_week_plan(post, dry_run=dry_run)

    header = (
        f"# Weekly Update — {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}\n"
        f"Duration: {duration_s:.0f}s  •  Status: {'ABORTED' if aborted else 'OK'}\n"
    )
    parts = [header]
    parts.append(_section("✅ Successes", upgraded))
    parts.append(_section("❌ Failures", failed))
    parts.append(_section("⏭ Skips", skipped))
    parts.append(_section("⚠ Warnings", warnings))
    parts.append(_section("🔍 Review items", review))
    parts.append(_section("📊 Size delta", size_lines))
    parts.append(_section("🔜 Next-week plan", next_week))
    return "\n".join(parts)


def _size_delta(pre: Snapshot, post: Snapshot) -> list[str]:
    # Lightweight: just compare hermes install dir size if both snapshots have it.
    pre_hermes = next((c for c in pre.components if c.name == "hermes"), None)
    post_hermes = next((c for c in post.components if c.name == "hermes"), None)
    if not (pre_hermes and post_hermes and pre_hermes.version_before != post_hermes.version_after):
        return []
    try:
        import subprocess
        out = subprocess.check_output(
            ["du", "-sh", "/usr/local/lib/hermes-agent"], text=True, timeout=30,
        ).strip()
    except Exception:
        out = "(du failed)"
    return [f"hermes install dir: {out}"]


def _next_week_plan(post: Snapshot, *, dry_run: bool) -> list[str]:
    if dry_run:
        return ["(dry-run; nothing planned — re-run for real on Monday)"]
    notes: list[str] = []
    for name in ("codex", "claude", "opencode", "openclaw", "pi"):
        c = next((x for x in post.components if x.name == name), None)
        if c and c.failure:
            notes.append(f"re-evaluate `{name}` upgrade on Monday")
    if not notes:
        notes.append("no follow-ups needed; everything green")
    return notes