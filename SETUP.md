# SETUP

> 远程源:`https://raw.githubusercontent.com/leiyunkang7/setup/main/SETUP.md`

把工具链和全局规则一次装齐。

**通用原则**:已装则跳,不覆盖现有配置(优先复用)。
**安装策略**:Linux/macOS 优先 brew,Windows 用 winget。

---

## 概览

按顺序完成 5 个 stage。每个 stage 有 _完成准则_,通过才能进入下一个;带 ⏸ 的 stage 含需要你手动操作的步骤,agent 会在那里停下来等你。

| #  | 内容                          | ⏸ |
|----|-------------------------------|----|
| 1  | 运行时(rust / bun / node)     | ⏸ |
| 2  | Shell(fish / pwsh7)+ 默认配置 | ⏸ |
| 3  | Agent(6 个)+ 插件             | ⏸ |
| 4  | MCP + 模型 + CLI 鉴权         | ⏸ |
| 5  | 全局规则(写入所有 agent)      | ⏸ |

---

## Stage 1 — 运行时 ⏸

**完成准则**:`rustc --version`、`bun --version`、`node --version` 三条命令都能输出。

- rust:https://rustup.rs
- bun:https://bun.sh
- nodejs:https://nodejs.org

⏸ 等三条命令都返回版本号,进入 Stage 2。

---

## Stage 2 — Shell 与默认配置 �

**完成准则**:`echo $SHELL` 是 fish 或 pwsh7;`atuin --version` 有输出;`git config --get core.editor` 返回 vim;vim 启动后默认显示行号。

按平台分支装并设为默认 shell。`atuin` 跨平台,两个平台都装。

- Linux/macOS:fish
- Windows:pwsh7

**默认配置**

- git 默认编辑器 vim
- vim 默认显示行号

⏸ 等 `$SHELL` 与 vim 行号都验证通过,进入 Stage 3。

---

## Stage 3 — Agent 与插件 ⏸

**完成准则**:6 个 agent 命令(`codex --version` 等)都能跑;技能目录非空。

### 编码 agent

codex / claude / pi / opencode

### 自主 agent

hermes / openclaw

### 插件

- opencode:https://github.com/alvinunreal/oh-my-opencode-slim
- 全局技能:`bunx skills@latest add mattpocock/skills`
- skillhub(CN 源):https://skillhub.cn/install/skillhub.md
  - 收录:`@tencent-adm/ima-skills`

⏸ 等 6 个 agent 与技能目录验证通过,进入 Stage 4。

---

## Stage 4 — MCP、模型与 CLI 鉴权 ⏸

**完成准则**:context7 / codegraph / cloudflare 在至少一个 agent 的 MCP 配置里可见;`gh auth status` 已登录。

### MCP

- context7 — https://context7.com/dashboard 拿 key
- codegraph — https://github.com/colbymchenry/codegraph
- cloudflare — 装官方 skills + MCP,配置 API key

### 模型

Minimax-M3,国内版 token plan。

### CLI 鉴权

`gh` — 引导 `gh auth login` 配 API key。

⏸ 等 API key 写入对应配置,`gh auth status` 显示已登录,进入 Stage 5。

---

## Stage 5 — 全局规则 �

**完成准则**:hermes / openclaw / claude / opencode / codex / pi 这 6 个 agent 的全局配置文件都包含以下 4 条规则。

**合并策略**:不覆盖现有配置,优先复用现有条目;如有重复则跳过。

写入 6 个 agent 的全局配置:

1. **第一性原理**:解决问题、修 BUG、设计架构或方案时,从第一性原理出发。
2. **对抗性审查**:相对复杂的任务完成后,开启多 Agent 对抗性审查。
3. **代理优先**:遇到网络问题,先排查系统代理。
4. **脚本栈**:默认 bun + ts。

⏸ 等 6 个 agent 的配置都验证通过。
