#!/usr/bin/env python3
"""Regression test for ADR 0005 — hermes update syncs skill category directories.

The decision (ADR 0005) is: `hermes update` is responsible for syncing bundled
skill category directories into `~/.hermes/skills/`. This test verifies the
**post-condition** that hermes is supposed to satisfy.

Observed reality on this host (2026-08-09 recon + post-update verification):

  /usr/local/lib/hermes-agent/skills/      → ALL non-cache dirs sync'd
  /usr/local/lib/hermes-agent/optional-skills/ → only the default opt-in set
                                                sync'd; the rest are user-opt-in

So this test is layered:

  1. **bundled_required**  — every non-cache directory under
     `/usr/local/lib/hermes-agent/skills/` MUST be present under
     `~/.hermes/skills/`. If this fails, hermes's bundled sync broke.

  2. **optional_default_synced** — verifies the small set of optional
     categories that hermes ships as default-on (autonomous-ai-agents,
     creative, data-science, devops, email, mlops, productivity, research,
     software-development) are present. Hermes's seed list can change; if this
     set shrinks or grows, the test needs an update — but a silent DROP means
     hermes changed its opt-in defaults, which deserves a human look.

  3. **manifest tracking** — the orchestrator's manifest must include
     `category_dirs` as a tracked component (ADR 0005's verify gate).

  4. **manifest helper** — `_hermes_skill_category_set` returns a stable
     comma-joined string or None; must not raise.

The test does NOT assert that every optional category is synced — those are
user-opt-in and legitimately absent unless the user enabled them.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import manifest  # pyright: ignore[reportMissingImports]


HERMES_SKILLS = Path("/usr/local/lib/hermes-agent/skills")
HERMES_OPTIONAL = Path("/usr/local/lib/hermes-agent/optional-skills")
HERMES_HOME = Path("/root/.hermes")

# Caches that live alongside real categories in bundled/. They start with `.`?
# No — `index-cache` doesn't. It's a hidden cache hermes rebuilds and is
# deliberately NOT a user-visible skill category.
BUNDLED_EXCLUDE = frozenset({"index-cache"})

# Optional categories that hermes ships as default-on (sync'd automatically).
# If Hermes changes this list, update this set — but verify the diff is
# intentional by reading hermes's CHANGELOG before adjusting.
OPTIONAL_DEFAULT = frozenset({
    "autonomous-ai-agents",
    "creative",
    "data-science",
    "devops",
    "email",
    "mlops",
    "productivity",
    "research",
    "software-development",
})


def _real_categories(root: Path, *, exclude: frozenset[str] = frozenset()) -> set[str]:
    """Non-hidden category names directly under `root` (symlinks included)."""
    out: set[str] = set()
    if not root.is_dir():
        return out
    for entry in root.iterdir():
        if entry.name.startswith("."):
            continue
        if entry.name in exclude:
            continue
        if entry.is_dir() or entry.is_symlink():
            out.add(entry.name)
    return out


class TestSkillCategoriesSync(unittest.TestCase):
    """ADR 0005 — bundled → ~/.hermes/skills/ sync post-condition."""

    def setUp(self) -> None:
        if not HERMES_SKILLS.is_dir():
            self.skipTest(f"{HERMES_SKILLS} not present on this host")

    def test_bundled_required_all_synced(self) -> None:
        """Every bundled category (minus caches) must reach ~/.hermes/skills/."""
        bundled = _real_categories(HERMES_SKILLS, exclude=BUNDLED_EXCLUDE)
        synced = _real_categories(HERMES_HOME / "skills")
        missing = sorted(bundled - synced)
        self.assertEqual(
            missing, [],
            f"Hermes bundled {len(missing)} category dir(s) that "
            f"`hermes update` has not synced into {HERMES_HOME}/skills/: "
            f"{missing}. Run `hermes update` to refresh. See ADR 0005.",
        )

    def test_optional_default_synced(self) -> None:
        """The default opt-in optional categories must reach ~/.hermes/skills/."""
        synced = _real_categories(HERMES_HOME / "skills")
        # Only assert categories that BOTH exist in optional AND are in our
        # default-set list. If optional/ doesn't exist on this hermes version
        # (e.g. older install), every default is vacuously satisfied.
        if not HERMES_OPTIONAL.is_dir():
            return
        available_optional = _real_categories(HERMES_OPTIONAL)
        expected = OPTIONAL_DEFAULT & available_optional
        missing = sorted(expected - synced)
        self.assertEqual(
            missing, [],
            f"Optional default categories missing from {HERMES_HOME}/skills/: "
            f"{missing}. Hermes's sync may have regressed, or the hermes "
            f"opt-in default list changed — check CHANGELOG and update "
            f"OPTIONAL_DEFAULT in this test if intentional. See ADR 0005.",
        )

    def test_manifest_tracks_category_dirs(self) -> None:
        spec = next(
            (s for s in manifest.TRACKED if s.get("name") == "category_dirs"),
            None,
        )
        self.assertIsNotNone(
            spec,
            "manifest.TRACKED is missing the `category_dirs` component — "
            "ADR 0005's verify gate is not wired.",
        )
        self.assertEqual(spec["category"], "skill_categories")  # type: ignore[index]

    def test_category_set_helper_returns_string(self) -> None:
        result = manifest._hermes_skill_category_set(str(HERMES_HOME))
        if result is not None:
            self.assertNotIn(" ", result, "category set should have no spaces")
            for name in result.split(","):
                self.assertTrue(name, "category name must be non-empty")


if __name__ == "__main__":
    unittest.main()
