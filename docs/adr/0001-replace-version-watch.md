# ADR 0001 — Replace weekly-version-watch with weekly-update-all

**Status**: accepted (originally two-cron plan; superseded by ADR 0006, which collapses to a single cron)

The existing `weekly-version-watch` cron (Mon 09:00 UTC, deliver=feishu) only reports stale versions and asks the user to act. The new `weekly-update-all` cron (Mon 04:00 Asia/Shanghai = `0 20 * * 0` UTC) actually performs upgrades and reports a digest. Both serve the user — one is a passive observer, the other is an active operator — so they are not equivalent and the passive one is removed.

The decision is to fully **replace** rather than **coexist** so the user has exactly one weekly cron to reason about. The deleted cron is `weekly-version-watch` (job_id `88dd35eddbdd`).

The original plan also called for a second `weekly-hermes-self-update` cron at Sunday 03:50 Asia/Shanghai. ADR 0006 collapses the two crons into one — the hermes self-update happens as the first phase of the same `weekly-update-all` run, with no daemon-interruption benefit from running it 24 hours earlier.