# ADR 0005 — Hermes skill category directories auto-update via `hermes update`

**Status**: accepted, implemented (policy enforced by ADR 0006's hermes-first pipeline ordering) + verified by `tests/test_skill_categories_sync.py`

Of the **13 skill category directories** under `~/.hermes/skills/` as of the 2026-08-09 recon (`apple`, `autonomous-ai-agents`, `creative`, `data-science`, `devops`, `email`, `github`, `media`, `mlops`, `note-taking`, `productivity`, `social-media`, `software-development`), 11 live under `/usr/local/lib/hermes-agent/skills/` (bundled) and 2 (`data-science`, `devops`) live under `/usr/local/lib/hermes-agent/optional-skills/`. **The exact split drifts** as Hermes ships new categories; treat the directory *names* and the bundled/optional split as a snapshot, not an invariant. The current host's bundled set has since grown (e.g. `research`, `smart-home` were not in the recon report), and the optional set has expanded too — never encode the count in the orchestrator.

`hermes update` calls `sync_skills(quiet=True)` and `seed_profile_skills(p.path, quiet=True)` which copy these into every profile's `~/.hermes/skills/` automatically, with hash-based skip on user-modified files. The weekly orchestrator therefore does **not** separately touch these directories — running `hermes update` once at the head of the single `weekly-update-all` pipeline is enough. This is implemented (not just decided): ADR 0006 makes Hermes the first step and isolates that step in a transient systemd worker, so the bundle ships before the next component upgrades.

A name in `~/.hermes/skills/` reaches one of two end-states after sync:
- **real directory** copied from Hermes's bundled/optional tree (the common case);
- **symlink** the user has placed, typically pointing at `/root/.agents/skills/<name>` — Hermes detects this and defers to the user's source rather than clobbering it. This is the user-takes-over path; it counts as "synced" because Hermes's sync would have produced a real dir, but the user has opted into a different source of truth.

`index-cache/` lives inside Hermes's bundled tree but is **not** a user-visible skill category — it's a Hermes internal cache (rebuilt on each update), and is excluded from the manifest's category set and the regression test.

Because the orchestrator does not drive sync itself, it must **verify** the post-`hermes update` state instead. Two layers:

1. **`scripts/lib/manifest.py`** — `category_dirs` is a tracked `Component` whose `version_before` / `version_after` is the sorted, dotfile-excluded name list of `~/.hermes/skills/` (real dirs **and** symlinks both count). `upgraders.upgrade_skill_categories` runs immediately after `upgrade_hermes` as a no-op snapshot pass — Hermes already did the sync; the orchestrator only observes. A warning is attached if `version_after != version_before` while Hermes's version also changed but the count of bundled categories didn't follow (i.e. sync silently skipped something). When neither side changed, no warning fires.
2. **`tests/test_skill_categories_sync.py`** — two post-conditions:
   - **bundled required**: every non-cache dir under `/usr/local/lib/hermes-agent/skills/` must appear under `~/.hermes/skills/` (as real dir or symlink).
   - **optional default**: the small set of optional categories Hermes ships as default-on (`autonomous-ai-agents`, `creative`, `data-science`, `devops`, `email`, `mlops`, `productivity`, `research`, `software-development`) must also appear. If Hermes changes that default list, the test needs an update; a silent DROP means Hermes changed its opt-in defaults, which deserves a human look at the CHANGELOG.
   - Plus two structural checks: `manifest.TRACKED` includes `category_dirs`, and `_hermes_skill_category_set` returns a stable comma-joined string without raising.

Consequence: when the user customised any SKILL.md under `~/.hermes/skills/`, `hermes update` will skip that file. The user is responsible for re-merging changes via `hermes skills list-modified` if a bundled update touches a customised file. The sync gate above does not flag customised files — Hermes's hash-based skip is correct and intentional.

If Hermes ever stops calling `sync_skills` automatically (regression), the bundled-required test fails immediately and the digest surfaces a warning. If Hermes ships a new category, the user runs the orchestrator once; the bundled count grows by 1, the orchestrator count grows by 1, no warning fires, and the test stays green.
