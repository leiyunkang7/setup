# ADR 0006 — Single `weekly-update-all` cron, not two

**Status**: accepted, implemented, and runtime-verified **on the host (2026-08)**. The single-cron decision, Hermes-first pipeline ordering, and process-isolation rationale below remain authoritative. The parts that relied on this repository's `scripts/` being a byte-identical source of truth for the deployed runtime are **retired by ADR 0007**: this repo is now documentation-only, and the running code lives at `~/.hermes/scripts/`.

**Amendment (2026-09)**: the deployed cadence is now **every three days**, cron `0 20 */3 * *` UTC (= next-day 04:00 Asia/Shanghai), not the original weekly `0 20 * * 0`. Only the cron expression changed when the schedule was adjusted from weekly to a three-day interval; the single-cron decision, Hermes-first ordering, and process-isolation rationale are unaffected.

ADR 0001 originally planned **two** cron jobs: a Sunday 03:50 Asia/Shanghai run that upgraded only Hermes itself, and a Monday 04:00 run that upgraded everything else. The reasoning was that the smaller hermes-only run would finish before the heavier Monday run, isolating hermes daemon interruption from other upgrades.

Runtime verification disproved the original claim that there was no Hermes daemon interruption to isolate:

- The orchestrator (`weekly-update.py`) is a one-shot Python script and no LLM loop is involved.
- However, `hermes update` intentionally drains and restarts every running Hermes gateway so each process loads the new code. The in-process cron scheduler and its script child live under `hermes-gateway.service`; without isolation, the first pipeline step kills the process that should execute the remaining steps.
- The solution is process isolation rather than a second schedule: `weekly-update.sh` launches the full pipeline as `hermes-weekly-update-worker.service`, a transient systemd service outside the gateway cgroup. The worker survives the gateway restart and continues the remaining upgrades and Feishu delivery.

The decision remains **one tool-update cron** — `weekly-update-all` at `0 20 * * 0` UTC (= Monday 04:00 Asia/Shanghai) — with Hermes first in the isolated worker's pipeline. The reporting-only `weekly-apt-security-watch` is a separate OS-security concern and is not a second update pipeline. A separate Sunday Hermes cron is unnecessary because process isolation, not elapsed time between schedules, is the invariant that keeps the broader run alive.

The deployed job is active in Hermes's cron store as `weekly-update-all`, uses `--no-agent --script weekly-update.sh`, and delivers locally because the detached worker sends the digest directly through hermes-side feishu (ADR 0003). Neither the deleted `weekly-version-watch` job nor the never-created `weekly-hermes-self-update` job may coexist with it. Hermes runs first in the isolated worker's pipeline; `category_dirs` immediately follows as a no-op verification gate for ADR 0005.

Durable contract (host-side): a test against the public `hermes cron list --all` state rejects either legacy second-job name and checks the schedule/script/no-agent mode. The byte-drift check between a version-controlled copy in `/root/code/setup/scripts/` and the deployed runtime was **retired with ADR 0007** — the repo no longer carries the runtime.

The destructive boundary is verified only with `--dry-run` on the host: launch the real wrapper as a transient worker, observe its PID and its `/system.slice/hermes-weekly-update-worker.service` cgroup, restart `hermes-gateway.service`, then confirm the worker PID/cgroup are unchanged and a complete digest is produced. This exercises the isolation boundary without invoking `hermes update` or any package manager.