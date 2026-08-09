# SETUP

`https://raw.githubusercontent.com/leiyunkang7/setup/main/SETUP.md`

装好工具链,把全局规则写入所有 agent 配置。

## 安装

全部装到全局,编码工具、agent 工具、技能统一一处管。

### 编码 agent

codex / claude / pi / opencode

### 自主 agent

hermes / openclaw

### 运行时

rust / bun / nodejs

### Shell

按平台分支装并设为默认 shell;atuin 跨平台,两个平台都装。

- Linux / macOS:fish
- Windows:pwsh7

### 插件

- opencode:`https://github.com/alvinunreal/oh-my-opencode-slim`
- 全局技能:`bunx skills@latest add mattpocock/skills`

## MCP

- context7 — `https://context7.com/dashboard` 拿 key
- codegraph — `https://github.com/colbymchenry/codegraph`
- cloudflare — 装官方 skills + MCP,配置 API key

## CLI 鉴权

`gh` — GitHub CLI,引导 `gh auth login` 配 API key。

## 模型

Minimax-M3,国内版 token plan。

## 默认配置

- git 默认编辑器 vim
- vim 默认显示行号

## 全局规则

写入 hermes / openclaw / claude / opencode / codex / pi 的全局配置:

1. **第一性原理**:解决问题、修 BUG、设计架构或方案时,从第一性原理出发。
2. **对抗性审查**:相对复杂的任务完成后,开启多 Agent 对抗性审查。

## 约定

写脚本默认 bun + ts。