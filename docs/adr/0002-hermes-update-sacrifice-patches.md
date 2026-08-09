# ADR 0002 — Hermes upgrades via its own `hermes update`, patches are sacrificed

**Status**: accepted (the "Sunday cron" portion is superseded by ADR 0006 — Hermes is now upgraded as the first phase of the single weekly-update-all pipeline at `0 20 * * 0` UTC, running in a transient systemd worker that survives the gateway restart. The patch-sacrifice policy and backup-snapshot requirement below remain authoritative.)

Hermes is git-installed at `/usr/local/lib/hermes-agent/`. Two patches previously applied by hand (MCP `mcp-` prefix acceptance in `cli.py:4485`, and `~/.local/bin` in subprocess env) will be overwritten by the next hermes upgrade. The user has decided to **accept the loss** rather than auto-reapply them: the patches were workarounds for transient issues, and re-applying on every hermes upgrade adds a non-trivial failure mode that defeats the purpose of an unattended weekly cron.

If the patches are ever needed again, they can be re-derived from the backup snapshots that `upgrade_hermes` (in `scripts/lib/upgraders.py`) writes to `~/.hermes/backups/pre-hermes-upgrade-<ts>/` before every hermes upgrade. Each backup contains:
- `patches.diff` — `git diff HEAD` of the working tree at backup time (tiny; this is the artifact that lets patches be reconstructed in seconds, not by untarring the snapshot)
- `hermes-agent.tar.gz` — full snapshot of `/usr/local/lib/hermes-agent/` (excluding `.git/`)
- `HEAD-pre.txt` — pre-upgrade git commit SHA, for provenance

The orchestrator rotates backups, keeping the 4 most recent. If the backup snapshot itself fails (tar/git error), the upgrade still proceeds but the digest surfaces a `⚠ Warning` for that step on Monday's review.