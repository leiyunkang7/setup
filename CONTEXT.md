# Weekly Update Orchestrator

A scheduled job that upgrades the user's full agent + tooling stack once a week, with manifest snapshots, health gates, and a markdown digest pushed to the hermes-side feishu channel.

## Language

**Weekly Update Run**:
One execution of the weekly-update-all cron job. A run has a start time, a manifest snapshot of "before" and "after" state, an ordered pipeline of upgrade steps, and a final digest.
_Avoid_: Sync, batch, tick

**Upgrade Step**:
A single, ordered action within a run (e.g. "hermes update", "rustup update", "npm i -g ..."). Each step has a name, a command, an expected exit-0 contract, and a list of skip entries.
_Avoid_: Task, job, action

**Manifest**:
The structured record of every tracked component's version + path + upgrade entry, captured twice per run (pre.json, post.json) so a diff can be computed.
_Avoid_: Inventory, snapshot

**Health Gate**:
A post-upgrade check that runs `<tool> --version` (and `--help`) for each upgraded tool. Failure on any gate aborts subsequent steps; previously-successful steps are not rolled back.
_Avoid_: Sanity check, smoke test

**Skip Entry**:
A package or tool deliberately excluded from a step (e.g. system apt packages, un-installed tools, closed-source binaries shipped with the OS). Skip entries live in a git-tracked file under the setup repo.
_Avoid_: Blocklist, ignore list

**Hermes-Side Feishu Channel**:
The feishu chat channel addressed by `FEISHU_HOME_CHANNEL` env var. Pushes from weekly-update go directly through hermes's own feishu client — NOT through OpenClaw's `channels.feishu` adapter.
_Avoid_: OpenClaw feishu, gateway feishu

**Digest**:
The markdown report pushed to the feishu channel at the end of a run. Eight sections: header, ✅ successes, ❌ failures, ⏭ skips, ⚠ warnings, 🔍 review items, 📊 size delta, 🔜 next-week plan.
_Avoid_: Summary, report

## Boundaries

- **In scope**: hermes, codex, claude, opencode, openclaw, pi, rustc, bun, node, npm, bun global packages, uv tools, the single-source `/root/.agents/skills/`, and hermes-bundled skill category directories.
- **Out of scope**: project-level skills (anything under a repo's `.claude/` or `AGENTS.md`), OS-level apt packages, brew (not installed), pwsh (not installed), system Python packages.
- **NOT rolled back on failure**: a partial run leaves successful upgrades in place and reports failures to feishu. The user reviews on Monday.