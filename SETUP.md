# SETUP

> 远程源:`https://raw.githubusercontent.com/leiyunkang7/setup/main/SETUP.md`

把工具链和全局规则一次装齐。

**通用原则**:已装则跳,不覆盖现有配置(优先复用)。
**安装策略**:Linux/macOS 优先 brew,Windows 用 winget。

---

## 概览

按顺序完成 5 个 stage。每个 stage 有 _完成准则_,通过才能进入下一个;带 ⏸ 的 stage 含需要你手动操作的步骤,agent 会在那里停下来等你。Stage 6 是安装后自动运行的维护(定时更新软件),无需手动步骤。

| #  | 内容                          | ⏸ |
|----|-------------------------------|----|
| 1  | 运行时(rust / bun / node)     | ⏸ |
| 2  | Shell(fish / pwsh7)+ 默认配置 | ⏸ |
| 3  | Agent(6 个)+ herdr + 插件 + cc-switch | ⏸ |
| 4  | MCP + 模型 + CLI 鉴权         | ⏸ |
| 5  | 全局规则(写入所有 agent)      | ⏸ |
| 6  | 定时更新软件(自动维护)        | —  |

---

## Stage 1 — 运行时 ⏸

**完成准则**:`rustc --version`、`bun --version`、`node --version`、`fnm --version` 四条命令都能输出。

- rust:https://rustup.rs
- bun:https://bun.sh
- node:用 fnm 安装管理(https://github.com/Schniz/fnm),不要官网直装——Stage 6 的 weekly-update 会跳过 node,依据就是"由 fnm 管理,更新走 fnm 不走 npm"(见 Stage 6 跳过清单),官网装的 node 会被 npm 全局更新误动

⏸ 等三条命令都返回版本号,进入 Stage 2。

---

## Stage 2 — Shell 与默认配置 ⏸

**完成准则**:`echo $SHELL` 是 fish 或 pwsh7;`atuin --version` 有输出;`git config --get core.editor` 返回 vim;vim 启动后默认显示行号。

按平台分支装并设为默认 shell。`atuin` 跨平台,两个平台都装。

- Linux/macOS:fish
- Windows:pwsh7

**默认配置**

- git 默认编辑器 vim
- vim 默认显示行号(验证:`vim -es -c 'set number?' -c qa`,应输出 `number`)

⏸ 等 `$SHELL` 与 vim 行号都验证通过,进入 Stage 3。

---

## Stage 3 — Agent 与插件 ⏸

**完成准则**:6 个 agent 命令(`codex --version` 等)都能跑;herdr 已安装(`herdr --version` 有输出);技能目录非空(`ls ~/.agents/skills | wc -l` > 0,含 herdr skill);cc-switch 已安装(macOS 看 `brew list --cask cc-switch`,Linux 看 `dpkg -l cc-switch`,Windows 为 MSI 或便携版)。

### 编码 agent

codex / claude / pi / opencode

### 自主 agent

hermes / openclaw

### herdr — 编码 agent 运行时

Rust 写的终端复用/常驻服务,让 agent 在后台终端里持续工作(合盖、断网、重启后仍可重连);单二进制,无 Electron。项目:https://github.com/herdrdev/herdr(文档 https://herdr.dev/docs)。

- 安装:`curl -fsSL https://herdr.dev/install.sh | sh` → `~/.local/bin/herdr`,与 Stage 6 weekly-update 的升级路径一致;macOS 也可 `brew install herdr`,Windows 用 `irm https://herdr.dev/install.ps1 | iex`(beta)
- skill:`npx skills add herdrdev/herdr --skill herdr -g`(全局安装;若此前装在仓库根目录的旧版,重跑一次 add 而非 `skills update`)
- 使用:先 `herdr` 启动,再在 herdr 终端里启动 agent(如 `herdrclaude`),agent 会拿到 `HERDR_ENV=1`,skill 的安全规则据此生效;`ctrl+b q` 分离,再 `herdr` 重连

### 插件

- opencode:https://github.com/alvinunreal/oh-my-opencode-slim
- 全局技能:`bunx skills@latest add mattpocock/skills`
- skillhub(CN 源):https://skillhub.cn/install/skillhub.md
  - 收录:`@tencent-adm/ima-skills`

### cc-switch — provider 切换管理

跨平台桌面应用,统一管理本工具链 agent(Claude Code / Codex / OpenCode / OpenClaw / Hermes 等)的 provider 切换,附带 MCP / Skills 统一管理,数据存 `~/.cc-switch/cc-switch.db`。自带自动更新,无需加入 weekly-update 管道。

- 项目:https://github.com/farion1231/cc-switch(官网 https://ccswitch.io,CN 直连下载)
- macOS:`brew install --cask cc-switch`(官方推荐)
- Windows:winget 暂无此包,从 GitHub Releases 下载 `CC-Switch-v<ver>-Windows.msi`(推荐,支持自动更新)或 `-Windows-Portable.zip`
- Linux:GitHub Releases 下载 `.deb` / `.rpm` / `.AppImage`,按 `uname -m` 选 x86_64 或 arm64

首次启动可手动导入现有 CLI 配置作为默认 provider;切换后需重启终端或对应 CLI 生效(Claude Code 例外,支持热切换)。

⏸ 等 6 个 agent、herdr(含 skill)、技能目录与 cc-switch 验证通过,进入 Stage 4。

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

## Stage 5 — 全局规则 ⏸

**完成准则**:hermes / openclaw / claude / opencode / codex / pi 这 6 个 agent 的全局配置文件都包含以下 5 条规则。

**规则定义**:唯一源是 [AGENTS.md](AGENTS.md) 的 `<!-- SETUP_GLOBAL_RULES_START/END -->` 标记块。本仓库只保留这一定义,不携带任何同步脚本/实现(ADR 0007);各 agent 的全局配置须与标记块内容一致,已有标记块则替换块内内容,没有则追加。合并策略:不覆盖现有配置,优先复用现有条目;如有重复则跳过。

⏸ 等 6 个 agent 的全局配置都与 AGENTS.md 标记块内容一致,进入 Stage 6。

---

## Stage 6 — 定时更新软件(自动维护,无手动步骤)

**完成准则**:`hermes cron list` 能看到 `weekly-update-all`(每 3 天 20:00 UTC = 次日 04:00 东八区,`0 20 */3 * *`)与 `weekly-apt-security-watch`(周一 08:00 UTC)。

安装完成后,本机由两套定时任务自动维护工具链,agent 不再手动盯版本。本仓库只保留这两条定时任务的 **md 定义**,不含实现;运行时实现位于主机侧 ~/.hermes/scripts,不是本仓库的版本化内容(ADR 0007)。

### weekly-update-all — 工具链周更

单条定时任务,每 3 天自动升级全量 agent + 工具链,结束时推送 digest 到飞书。

- **调度**:每 3 天 20:00 UTC = 次日 04:00 东八区(`0 20 */3 * *`);任一升级步骤失败即中止后续步骤
- **覆盖范围**:hermes、codex / claude / openclaw(npm 全局)、opencode(bun 全局)、pi、rustc(rustup)、npm 全局包、bun 全局包、uv tools、yazi / herdr(GitHub 预编译 release)、技能仓库 /root/.agents/skills
- **跳过清单**:apt / dpkg / pwsh / brew / skills / pip / node 等由各自机制管理、不属于本管道的工具(如 node 走 fnm、cc-switch 自带自动更新)
- **产物**:每次运行生成升级前后快照对比 + digest,经 hermes 侧飞书渠道推送(ADR 0003),保留最近若干份
- **策略**:hermes 升级前备份可重建补丁(ADR 0002);升级顺序 hermes 置首、进程隔离防重启自杀(ADR 0006);hermes update 会同步 skill 分类目录(ADR 0005)

### weekly-apt-security-watch — 系统安全更新巡检

单条**只报告、不升级**的系统安全巡检。

- **调度**:周一 08:00 UTC = 周一 16:00 东八区,agent 模式(ask-matt),推送飞书
- **行为**:只读本地 apt 元数据输出报告;**绝不**执行 `apt upgrade / install`;元数据超 7 天未刷新时提示先 `sudo apt update`

> 设计依据:`docs/adr/0001..0006`。本仓库为纯文档,运行时唯一真源在主机侧 ~/.hermes/scripts(ADR 0007)。
