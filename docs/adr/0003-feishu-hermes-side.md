# ADR 0003 — Weekly digest pushes through hermes-side feishu, not OpenClaw

**Status**: accepted

Two feishu channels exist on this host: hermes's own (driven by `FEISHU_*` env vars and a hermes-internal lark/feishu SDK client) and OpenClaw's `channels.feishu` adapter (driven by `~/.openclaw/openclaw.json` appId/appSecret). Existing cron jobs that say `deliver=feishu` actually flow through OpenClaw — that is the path the orchestrator **explicitly avoids**.

Reason: the weekly-update orchestrator is a hermes-managed artifact. Routing its digest through a separate agent (OpenClaw) introduces a second failure domain and obscures which system produced the message. Direct use of the hermes-side feishu client keeps the orchestrator self-contained.

Implementation: the orchestrator script imports the hermes-internal feishu client (or, if hermes does not expose one, calls the lark SDK directly with the same `FEISHU_*` env vars) and posts the digest as a markdown message to `FEISHU_HOME_CHANNEL` (thread_id from `FEISHU_HOME_CHANNEL_THREAD_ID` if set).