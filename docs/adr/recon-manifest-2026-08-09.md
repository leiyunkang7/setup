# Machine Reconnaissance Manifest — Round 1

- **Date:** 2026-08-09
- **Host:** Linux 7.0.0-28-generic, headless
- **Workspace:** /root/code/setup
- **Shell:** fish 4.2.1
- **Python:** /usr/bin/python3 → 3.14.4 (PEP 668, no pip; uv 0.11.19 at /root/.hermes/bin/uv)
- **Purpose:** Read-only inventory for designing a weekly auto-update cron. No upgrade/install/run was performed.

---

## Section 1 — Binary probe + versions

| Command | Exit | stdout |
|---|---|---|
| `which hermes && hermes --version` | 0 | `/root/.local/bin/hermes` → `Hermes Agent v0.20.0 (2026.8.3)` / Install dir `/usr/local/lib/hermes-agent` / Python 3.11.15 / OpenAI SDK 2.24.0 |
| `which codex && codex --version` | 0 | `/run/user/0/fnm_multishells/.../bin/codex` → `codex-cli 0.147.0` |
| `which claude && claude --version` | 0 | `/run/user/0/fnm_multishells/.../bin/claude` → `2.1.226 (Claude Code)` |
| `which opencode && opencode --version` | 0 | `/root/.bun/bin/opencode` → `1.18.15` |
| `which openclaw && openclaw --version` | 0 | `/run/user/0/fnm_multishells/.../bin/openclaw` → `OpenClaw 2026.6.11 (e085fa1)` |
| `which pi && pi --version` | 0 | `/root/.hermes/node/bin/pi` → `0.84.1` |
| `which rustc && rustc --version` | 0 | `/root/.cargo/bin/rustc` → `rustc 1.96.0 (ac68faa20 2026-05-25)` |
| `which bun && bun --version` | 0 | `/root/.bun/bin/bun` → `1.3.14` |
| `which node && node --version` | 0 | `/run/user/0/fnm_multishells/.../bin/node` → `v26.4.0` |
| `which npm && npm --version` | 0 | `/run/user/0/fnm_multishells/.../bin/npm` → `11.17.0` |
| `which bunx && bunx --version` | 0 | `/root/.bun/bin/bunx` → `1.3.14` |
| `which pip && pip --version` | 1 | not found (no stdout) |
| `python3 -m pip --version` | 1 | `/usr/bin/python3: No module named pip` |
| `which gh && gh --version` | 0 | `/usr/bin/gh` → `gh version 2.46.0 (2025-12-13 Ubuntu 2.46.0-4)` |
| `which fish && fish --version` | 0 | `/usr/bin/fish` → `fish, version 4.2.1` |
| `which atuin && atuin --version` | 0 | `/root/.atuin/bin/atuin` → `atuin 18.16.1 (671f96b60dac49d1d2de73cc0812986a5e22ce7b)` |
| `which vim && vim --version \| head -1` | 0 | `/usr/bin/vim` → `VIM - Vi IMproved 9.1 (2024 Jan 02, compiled Jul 13 2026 17:06:53)` |
| `which pwsh && pwsh --version` | 1 | not found |
| `which skills && skills --version` | 1 | not found (no skillhub CLI) |

**Additional binaries surfaced incidentally:**
- `codegraph` → `/root/.local/bin/codegraph` → `1.0.1` (used by MCP servers)
- `ctx7` → `/root/.bun/bin/ctx7` → `0.5.3` (context7 CLI client)
- `uv` → `/root/.hermes/bin/uv` → `uv 0.11.19`

---

## Section 2 — Global skills directories

Counted "skill directories" = entries with a `SKILL.md` inside (depth ≤2). Real skills vs category folders are noted.

### `~/.hermes/skills/` — **exists**
- Top-level entries: **70** (mix of real skills + category folders)
- `SKILL.md` files at depth ≤3: **95**
- Real skills at depth 1 (have SKILL.md directly): **7**
  - `calibrate-user-context`, `cloudflare`, `code-review-axis-slice`, `github-push-fallback`, `ima-skill`, `reverse-review`, `version-watch`
- Category folders at depth 1: `apple`, `autonomous-ai-agents`, `creative`, `data-science`, `devops`, `email`, `github`, `media`, `mlops`, `note-taking`, `productivity`, `social-media`, `software-development` (each holds 1-N subskills)
- Many top entries are symlinks → `/root/.agents/skills/<name>` (the shared source of truth, 49 dirs)

### `~/.hermes/profiles/default/skills/` — **DOES NOT EXIST**
- `ls: cannot access '/root/.hermes/profiles/default/skills/'`
- → no profile-level override; default profile just uses `~/.hermes/skills/` (verified by `~/.hermes/` containing `config.yaml`, `cron/`, etc., and no `profiles/` subdir)

### `~/.claude/skills/` — **exists**
- Top-level entries: **50** (mostly symlinks → `/root/.agents/skills/<name>`; some → `/root/code/skills/skills/productivity/cloudflare`; some real: `eve-evals-overview`, `grill-me-doc`)
- `SKILL.md` files at depth ≤3: **2**

### `~/.codex/skills/` — **exists** (only system skills)
- Contains: `.system/` subdir only
- `.system/` sub-skills (all 6 have `SKILL.md`): `imagegen`, `openai-docs`, `plugin-creator`, `review-agent`, `skill-creator`, `skill-installer`
- Plus marker: `.codex-system-skills.marker`

### `~/.pi/skills/` / `~/.config/pi/skills/` — **DO NOT EXIST**
- Pi keeps state under `~/.pi/agent/` (settings, auth, models-store, sessions, `skills/` which has 12 entries — `~/.pi/agent/skills/`)

### `~/.opencode/skills/` / `~/.opencode/` — **DO NOT EXIST**
- OpenCode uses **`~/.config/opencode/skills/`** — exists with 7 sub-skills (no SKILL.md inside any — these are opencode-style skill dirs): `clonedeps`, `codemap`, `deepwork`, `oh-my-opencode-slim`, `reflect`, `simplify`, `worktrees`

### `~/.openclaw/skills/` — **exists**
- Top-level entries: **45** (almost all symlinks → `/root/.agents/skills/<name>`)
- No SKILL.md at depth ≤3 (the real SKILL.md files live in the link targets)

### `~/.openclaw/plugin-skills/` — **exists** (extra location, not asked but worth noting)
- 6 entries: `browser-automation`, `canvas`, `feishu-doc`, `feishu-drive`, `feishu-perm`, `feishu-wiki` (all have SKILL.md)

### Project-level `/root/code/setup/.claude/skills/` — **DOES NOT EXIST**
### Project-level `/root/code/setup/skills/` — **DOES NOT EXIST**
- `/root/code/setup/` only contains: `SETUP.md`, `.claude/settings.local.json`, `.git/`, `docs/adr/`

---

## Section 3 — MCP servers configuration

### `~/.hermes/config.yaml` — exists (14603 bytes)
- `mcp_servers:` block (line 590): 2 entries
  - **`codegraph`** (stdio): `command: /root/.local/bin/codegraph`, args `serve --mcp`, enabled ✅ (binary present locally)
  - **`context7`** (remote HTTP): `url: https://mcp.context7.com/mcp`, headers include API key ⚠️ (cloud-only, no local binary)
- `platform_toolsets:` block (line 566): references `mcp-codegraph` under `cli`

### `~/.claude/settings.json` — exists
- `mcpServers:` block (line 118): 1 entry
  - **`cloudflare`** (stdio, type): runs `mcp-server-cloudflare` from `$HOME/.config/cloudflare-mcp/.env` ⚠️ (cloud service; binary lives in npm-global node_modules)

### `~/.claude.json` — exists (13568 bytes)
- 7 occurrences of `"mcpServers":` but **6 are empty `{}`** (per-project/per-workspace bookkeeping)
- Only **line 387** has a real entry: **`codegraph`** (stdio, command `codegraph serve --mcp`) — same as hermes

### `~/.codex/config.toml` — exists but **0 bytes** (empty)
- No MCP section. (`~/.config/codex/config.toml` does not exist.)

### `~/.config/opencode/opencode.jsonc` — exists
- `mcp:` block: 2 entries
  - **`codegraph`** (local): command `["codegraph", "serve", "--mcp"]`, enabled ✅
  - **`context7`** (remote): url `https://mcp.context7.com/mcp` with API key ⚠️

### `~/.openclaw/openclaw.json` — exists
- Under `channels.feishu` (not MCP), but the `mcporter` section lists many known MCP server names: `1password`, `blogwatcher`, `blucli`, `camsnap`, `coding-agent`, `eightctl`, `gemini`, `gifgrep`, `gog`, `goplaces`, `himalaya`, `mcporter`, `nano-pdf`, `obsidian`, `openai-whisper`, `openai-whisper-api`, `openhue`, `oracle`, `ordercli`, `sag`, `sherpa-onnx-tts`, `songsee`, `sonoscli`, `spotify-player`, `summarize`, `trello` — **all `enabled: false`**. (Catalog, not active config.)

### `~/.pi/agent/settings.json` — exists
- No `mcp` keys. Just `defaultProvider`, `defaultModel`, `theme`, `defaultThinkingLevel`, `images.blockImages`, `defaultProjectTrust`, `treeFilterMode`, `lastChangelogVersion`.

### Cloud-only MCP servers (name in config but no local `which`):
- **`context7`** — HTTP-only, hits `https://mcp.context7.com/mcp` (hermes + opencode). API key: `ctx7sk-4506ba89-...` in both.
- **`cloudflare`** — stdio-launched cloudflare-mcp-server (claude settings.json).

---

## Section 4 — Package manager upgrade entry points

| Tool | Present | Path / version | Upgrade entry |
|---|---|---|---|
| `rustup` | yes | `/root/.cargo/bin/rustup`, `rustup 1.29.0` (active rustc 1.96.0) | `rustup update` |
| `brew` | **no** | `command not found` | n/a |
| `apt` | yes | `/usr/bin/apt`, `apt 3.2.0 (amd64)` | skipped per spec |
| `npm` | yes (via fnm) | `11.17.0` | `npm i -g ...` |
| `bun` | yes | `1.3.14` | `bun add -g ...` |
| `pip` | **no** | not installed at OS level; `python3 -m pip` returns "No module named pip" | n/a (use `uv`) |
| `uv` | yes | `/root/.hermes/bin/uv` → `uv 0.11.19` | `uv tool upgrade ...` |

### `npm ls -g --depth=0` (full output, only 5 packages)
```
/root/.local/share/fnm/node-versions/v26.4.0/installation/lib
├── @anthropic-ai/claude-code@2.1.226
├── @cloudflare/mcp-server-cloudflare@0.2.0
├── @openai/codex@0.147.0
├── npm@11.17.0
└── openclaw@2026.6.11
```

### `bun pm ls -g` (full output, but only 3 top-level packages reported)
```
/root/.bun/install/global node_modules (85)   ← header says 85, but the tree only lists 3
├── agent-browser@0.33.2
├── ctx7@0.5.3
└── opencode-ai@1.18.15
```
**Caveat:** bun's `pm ls -g` reports "(85)" but only shows top-level bins. Inspecting `/root/.bun/install/global/node_modules/` directly: **300 packages** total, with **30 binaries** in `.bin/` including `agent-browser`, `ast-grep`, `ctx7`, `figlet`, `opencode`, `parser`, `pixelmatch`, `sg`, `tsc`, `tsserver`, `uuid`, `yaml`, etc.

### `pip list --user` / `python3 -m pip list --user` — both fail (no pip)

---

## Section 5 — Hermes cronjobs

### CLI subcommand (not a separate binary)
- `which cronjob` → not found
- `hermes cron --help` → `usage: hermes cron {list,create,add,edit,pause,resume,run,remove,rm,delete,status,runs,history,notepad,tick}`
- The context note said "cronjob action=create|list" — that's wrong; it's **`hermes cron <verb>`**, not `cronjob`.

### `hermes cron list` — 2 active jobs

```
88dd35eddbdd [active]
  Name:      weekly-version-watch
  Schedule:  0 9 * * 1      (Mon 09:00 UTC)
  Repeat:    ∞
  Next run:  2026-08-10T09:00:00+00:00
  Deliver:   feishu
  Skills:    ask-matt
  Last run:  2026-08-03T10:02:02  ok
  Execution: completed  5e66217c10a54e669922015f3aa0c70c

3545c90f1e66 [active]
  Name:      weekly-apt-security-watch
  Schedule:  0 8 * * 1      (Mon 08:00 UTC)
  Repeat:    ∞
  Next run:  2026-08-10T08:00:00+00:00
  Deliver:   feishu
  Skills:    ask-matt
  Last run:  2026-08-03T10:03:15  ok
  Execution: completed  8dcf5af2ae184071b4fd54c21537759a
```

Both already deliver to **feishu** — that's the existing channel wiring. State lives at `~/.hermes/cron/jobs.json` + `executions.db`.

---

## Section 6 — Feishu / Lark / Webhook status

### `~/.hermes/.env` (filenames/keys only — values redacted)
FEISHU keys present (and commented TELEGRAM_WEBHOOK_* keys):
```
FEISHU_APP_ID
FEISHU_APP_SECRET
FEISHU_DOMAIN
FEISHU_CONNECTION_MODE
FEISHU_ALLOW_ALL_USERS
FEISHU_ALLOWED_USERS
FEISHU_GROUP_POLICY
FEISHU_HOME_CHANNEL
FEISHU_HOME_CHANNEL_THREAD_ID
```
(Plus commented-out `TELEGRAM_WEBHOOK_URL`, `TELEGRAM_WEBHOOK_PORT`, `TELEGRAM_WEBHOOK_SECRET`, `TEAMS_PORT`.)

### `~/.hermes/config.yaml`
- **No** `feishu` / `lark` / `webhook` text under top-level keys.
- However, FEISHU_* env vars are read by the gateway/platform code (evidenced by `feishu_seen_message_ids.json` having ~90+ entries).

### Active runtime signals
- `~/.hermes/feishu_seen_message_ids.json` exists, **5829 bytes**, last modified Aug 9 06:54 — has been receiving traffic.
- `~/.hermes/cron/output/{88dd35eddbdd,3545c90f1e66}/2026-08-03_*.md` — last week's cron reports were pushed to feishu.
- Env vars at runtime: `FEISHU_CONNECTION_MODE=websocket`, `FEISHU_GROUP_POLICY=open`, `FEISHU_HOME_CHANNEL_THREAD_ID=` (empty).

### `~/.openclaw/openclaw.json` → `channels.feishu` (already wired up, full config)
```
enabled: true
dmPolicy: allowlist
appId: cli_aac0cd4fadf8dbc6
appSecret: 25ZmAZEFoUJd7oDCeSVxWh7WZqT7wRJv
allowFrom: [ou_35e068c836eeeaa3777b1e0ef887df4b]
groupAllowFrom: [ou_35e068c836eeeaa3777b1e0ef887df4b]
```
**Note for Round 2:** feishu channel is **already active via OpenClaw**, not just a future plan. The user's weekly cronjobs already `Deliver: feishu` and OpenClaw handles the push.

### `~/.openclaw/plugin-skills/` includes feishu-specific skills
- `feishu-doc/`, `feishu-drive/`, `feishu-perm/`, `feishu-wiki/`, `browser-automation/`, `canvas/`

### Environment variables (live)
```
FEISHU_CONNECTION_MODE=websocket
FEISHU_GROUP_POLICY=open
FEISHU_HOME_CHANNEL_THREAD_ID=
```
(no LARK_*, no WEBHOOK_* at runtime; webhook references only in commented `.env` template)

---

## Summary table

| 类别 | 工具 | 已装 | 版本 | 升级入口 | 备注 |
|---|---|---|---|---|---|
| Agent (Python wheel) | hermes | yes | v0.20.0 (2026.8.3) | `hermes update` 或 git pull at `/usr/local/lib/hermes-agent` | 已打过 2 个 MCP patch,upgrade 会丢 |
| Agent CLI (node) | codex | yes | codex-cli 0.147.0 | `npm i -g @openai/codex` | fnm 多版本壳 |
| Agent CLI (node) | claude | yes | 2.1.226 (Claude Code) | `npm i -g @anthropic-ai/claude-code` | fnm 多版本壳 |
| Agent CLI (node) | opencode | yes | 1.18.15 | `bun add -g opencode-ai` | |
| Agent CLI (node) | openclaw | yes | 2026.6.11 (e085fa1) | `npm i -g openclaw` | fnm 多版本壳 |
| Agent CLI (node) | pi | yes | 0.84.1 | bundled in `~/.hermes/node/lib/node_modules/@earendil-works/pi-coding-agent` | 通过 hermes node 路径 |
| Language runtime | rustc | yes | 1.96.0 (2026-05-25) | `rustup update` | rustup 1.29.0 |
| Language runtime | bun | yes | 1.3.14 | `bun upgrade` (官方) 或重装 | 自带 `bunx` |
| Language runtime | node | yes | v26.4.0 | fnm-managed | |
| Package manager | npm | yes | 11.17.0 | `npm i -g ...` | |
| Package manager | bunx | yes | 1.3.14 | 随 bun | |
| Package manager | pip | **no** | — | n/a | PEP 668; 系统无 pip |
| Package manager | uv | yes | 0.11.19 | `uv self update` / `uv tool upgrade` | `/root/.hermes/bin/uv` |
| Package manager | rustup | yes | 1.29.0 | `rustup update` | |
| Package manager | brew | **no** | — | n/a | Linux 上不存在 |
| Package manager | apt | yes | apt 3.2.0 (amd64) | skipped by policy | |
| VCS CLI | gh | yes | 2.46.0 | `apt upgrade gh` (system) | |
| Shell | fish | yes | 4.2.1 | `apt upgrade fish` (system) | |
| Shell history | atuin | yes | 18.16.1 | 重装 / cargo install | |
| Editor | vim | yes | 9.1 | `apt upgrade vim` | |
| CLI client | ctx7 | yes | 0.5.3 | `bun add -g ctx7` | context7 的客户端 |
| CLI client | codegraph | yes | 1.0.1 | 重装 / `pip install` | `/root/.local/bin/codegraph` |
| Powershell | pwsh | **no** | — | n/a | Linux 没装 |
| Skillhub CLI | skills | **no** | — | n/a | 没有这个 CLI |
| MCP server (local) | codegraph | yes | 1.0.1 | 重装 | hermes / opencode / claude 都在用 |
| MCP server (cloud) | context7 | n/a | https://mcp.context7.com/mcp | 改 key | hermes + opencode 用 |
| MCP server (cloud) | cloudflare | yes (npm) | 0.2.0 | `npm i -g @cloudflare/mcp-server-cloudflare` | 仅 claude settings.json |
| Feishu channel (Hermes) | — | partial | websocket / allowlist | config.yaml 没 ch. feishu 顶层块;env vars 已有 | 已有 cron deliver=feishu 在跑 |
| Feishu channel (OpenClaw) | — | **active** | enabled=true | `openclaw.json` 已配 appId/appSecret | **真正的推送通道** |
| Cron scheduler | hermes cron | yes | (in hermes) | `hermes cron {list,create,...}` | 2 个 weekly 任务已存在 |

---

## Round 1 fact-takes (for Round 2)

1. **`cronjob` is not a binary** — it's `hermes cron <verb>`. The context note is wrong; use `hermes cron list|create|edit|...`.
2. **No `pip`, no `brew`, no `pwsh`, no `skills` CLI** — Python upgrades must go via `uv`; nothing else to upgrade for system Python.
3. **Two MCP servers matter locally**: `codegraph` (local stdio, all three agents use it) and `context7` (cloud, same API key in hermes + opencode). Cloudflare MCP only in claude settings.
4. **Skills dir is shared via symlinks** at `/root/.agents/skills/` — that's the single source of truth. Hermes/Claude/OpenClaw all symlink into it. Categories (`apple`, `creative`, `devops`, etc.) are hermes-only and not symlinked.
5. **Pi has no skills dir** — it stores everything under `~/.pi/agent/`.
6. **OpenCode uses different convention**: `~/.config/opencode/skills/` with category-style subdirs and no SKILL.md inside (oh-my-opencode-slim, codemap, etc.).
7. **Codex has only system skills** under `~/.codex/skills/.system/` (6 subdirs, all have SKILL.md). User-level codex skills are absent.
8. **Project `/root/code/setup/` has no skills/** — only `SETUP.md` + `.claude/settings.local.json` + `.git/`.
9. **Feishu channel is already active through OpenClaw**, not Hermes. Both cron jobs already `Deliver: feishu`. Hermes only reads FEISHU_* env vars (no `channels.feishu:` block in `~/.hermes/config.yaml`).
10. **Two weekly cron jobs already exist** (`weekly-version-watch` Mon 09:00, `weekly-apt-security-watch` Mon 08:00). The "weekly-update" design should integrate with these or replace one.
11. **Hermes install is git-installed at `/usr/local/lib/hermes-agent/`** — `hermes update` would overwrite the two MCP patches the user mentioned.
12. **bun `pm ls -g` is misleading**: header says "(85)" packages but only 3 listed; actual `node_modules/` has 300 entries. For weekly-update purposes, prefer reading `/root/.bun/install/global/node_modules/` directly.
13. **No `~/.hermes/profiles/default/skills/`** — profile-level override doesn't exist; default uses `~/.hermes/skills/`.