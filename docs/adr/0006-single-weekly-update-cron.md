# ADR 0006 — Single `weekly-update-all` cron, not two

**Status**: accepted, implemented, and runtime-verified (supersedes the two-cron plan in ADR 0001)

ADR 0001 originally planned **two** cron jobs: a Sunday 03:50 Asia/Shanghai run that upgraded only Hermes itself, and a Monday 04:00 run that upgraded everything else. The reasoning was that the smaller hermes-only run would finish before the heavier Monday run, isolating hermes daemon interruption from other upgrades.

Runtime verification disproved the original claim that there was no Hermes daemon interruption to isolate:

- The orchestrator (`weekly-update.py`) is a one-shot Python script and no LLM loop is involved.
- However, `hermes update` intentionally drains and restarts every running Hermes gateway so each process loads the new code. The in-process cron scheduler and its script child live under `hermes-gateway.service`; without isolation, the first pipeline step kills the process that should execute the remaining steps.
- The solution is process isolation rather than a second schedule: `weekly-update.sh` launches the full pipeline as `hermes-weekly-update-worker.service`, a transient systemd service outside the gateway cgroup. The worker survives the gateway restart and continues the remaining upgrades and Feishu delivery.

The decision remains **one tool-update cron** — `weekly-update-all` at `0 20 * * 0` UTC (= Monday 04:00 Asia/Shanghai) — with Hermes first in the isolated worker's pipeline. The reporting-only `weekly-apt-security-watch` is a separate OS-security concern and is not a second update pipeline. A separate Sunday Hermes cron is unnecessary because process isolation, not elapsed time between schedules, is the invariant that keeps the broader run alive.

The deployed job is active in Hermes's cron store as `weekly-update-all`, uses `--no-agent --script weekly-update.sh`, and delivers locally because the detached worker sends the digest directly through `lib/feishu.py`. Neither the deleted `weekly-version-watch` job nor the never-created `weekly-hermes-self-update` job may coexist with it. The repository's `weekly-update.py` orders `hermes` before every other real upgrade step; `category_dirs` immediately follows as a no-op verification gate for ADR 0005.

`tests/test_single_weekly_update_cron.py` is the durable contract. It verifies the public `hermes cron list --all` state, rejects either legacy second-job name, checks the schedule/script/no-agent mode, proves Hermes runs first even when input components are unordered, and detects byte drift between the version-controlled runtime files and the copies under the active `$HERMES_HOME/scripts/` deployment.

The destructive boundary is verified only with `--dry-run`: launch the real wrapper as a transient worker, observe its PID and `/system.slice/hermes-weekly-update-worker.service` cgroup, restart `hermes-gateway.service`, then confirm the worker PID/cgroup are unchanged and a complete digest is produced. This exercises the isolation boundary without invoking `hermes update` or any package manager.