# ADR 0006 — Single `weekly-update-all` cron, not two

**Status**: accepted (supersedes the two-cron plan in ADR 0001)

ADR 0001 originally planned **two** cron jobs: a Sunday 03:50 Asia/Shanghai run that upgraded only Hermes itself, and a Monday 04:00 run that upgraded everything else. The reasoning was that the smaller hermes-only run would finish before the heavier Monday run, isolating hermes daemon interruption from other upgrades.

After implementation it turned out there is no hermes daemon interruption to isolate:

- The orchestrator (`weekly-update.py`) is a one-shot Python script. `--no-agent` mode runs it under cron, captures stdout, and exits. No hermes agent loop is involved.
- `hermes update` (the orchestrator's hermes phase) is `git pull` inside `/usr/local/lib/hermes-agent/`, which does not restart the cron scheduler or any running CLI session.
- Skipping a hermes self-update 10 hours before the broader update does not reduce risk: the same `git pull` happens either way; what matters is whether the *currently running* cron daemon survives, and it does.

The decision is to keep **one** cron — `weekly-update-all` at `0 20 * * 0` UTC (= Monday 04:00 Asia/Shanghai) — and let the orchestrator's pipeline order hermes first so any hermes CLI change is in place before the other 9 tools run.