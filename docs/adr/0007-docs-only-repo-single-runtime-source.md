# ADR 0007 — Setup repo is documentation-only; weekly-update runtime lives on the host

**Status**: accepted (2026-09)

The `/root/code/setup` repository previously carried **both** the installation guide and the full weekly-update implementation: `scripts/*.py` (orchestrator + `lib/` modules), `scripts/sync-rules.ts` (Stage 5 rule-sync tool), `tests/*.py|sh`, and ADRs 0001–0006 whose tests enforced a byte-identical copy of the runtime under `~/.hermes/scripts/`.

**Why it changed**: the repository's purpose is to document the machine's setup — what is installed, the global rules, and the scheduled tasks. The weekly-update runtime actually lives and runs at `~/.hermes/scripts/`; the repo copy existed only for version control and a deploy byte-check. Keeping a duplicate added maintenance burden and made the repo read like an implementation repo rather than a definition. The user asked the repo to carry the **md definitions only** for the scheduled-update software (`定时更新软件`), stripping the concrete implementation.

**Decision**:
- The repo no longer version-controls `scripts/` or `tests/`; both were removed. The repo is now documentation-only: `AGENTS.md`, `CONTEXT.md`, `SETUP.md`, and `docs/adr/`.
- The sole source of truth for the running runtime is the host: `~/.hermes/scripts/` (`weekly-update.py`, `weekly-update.sh`, `lib/`, `version-watch/`, `skip.txt`). Changes to the pipeline now happen in place on the host, guided procedurally by the auto-update-pipeline skill, not by editing a copy in this repo.
- `scripts/sync-rules.ts` was also removed. Stage 5 now states the rule definition only — the `AGENTS.md` marker block remains the single source of the 5 global rules; the 6 agent configs carry those rules. Any sync tooling, if it is ever re-added, lives host-side rather than being versioned here.
- The byte-identical deploy contract and its tests from ADR 0006 are **retired**.

**Consequence / trade-off**: a fresh machine can still reproduce the *definition* (install stages, global rules, scheduled-task list), but re-running certain tooling (e.g. a Stage 5 rule sync or a weekly-update dry run) requires pulling the tool from the host rather than from this repo. The design decisions in ADRs 0001–0006 remain authoritative for *what* is installed and *why*; their references to `/root/code/setup/scripts/` are now historical.