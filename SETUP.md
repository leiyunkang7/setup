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
- node:用 fnm 安装管理(https://github.com/Schniz/fnm),不要官网直装——Stage 6 的 weekly-update 跳过 node 的依据就是"由 fnm 管理,更新走 fnm 不走 npm"(scripts/skip.txt),官网装的 node 会被 npm 全局更新误动

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

**合并策略**:不覆盖现有配置,优先复用现有条目;如有重复则跳过。规则以 [AGENTS.md](AGENTS.md) 的 `<!-- SETUP_GLOBAL_RULES_START/END -->` 标记块为唯一源。

同步脚本:`bun run scripts/sync-rules.ts --apply`(默认 dry-run,只打印 digest 不写文件;`--agent-file <name>=<path>` 可覆盖各 agent 配置路径,Windows 必用)。每个被写入的文件先备份到 `~/.setup-backups/<ts>/`;已有标记块的文件只替换块内内容,没有的则在末尾追加。以后改规则只改 AGENTS.md 再重跑即可,不再手工逐条写。

⏸ 等 `bun run scripts/sync-rules.ts`(dry-run)对 6 个 agent 全部显示 up-to-date。

---

## Stage 6 — 定时更新软件(自动维护,无手动步骤)

**完成准则**:`hermes cron list` 能看到 `weekly-update-all`(周日 20:00 UTC = 周一 04:00 东八区)与 `weekly-apt-security-watch`(周一 08:00 UTC);`~/.hermes/scripts/weekly-update.sh --dry-run` 能产出 digest 且不执行任何真实升级。

安装完成后,本机已有两套定时任务自动维护工具链,agent 不再手动盯版本。

### weekly-update-all — 工具链周更

- 调度:`0 20 * * 0`(周日 20:00 UTC = 周一 04:00 东八区),`--no-agent --script weekly-update.sh`,deliver=local(飞书推送由脚本内 lib/feishu.py 完成)
- 入口:`~/.hermes/scripts/weekly-update.sh` → transient systemd worker `hermes-weekly-update-worker.service` → hermes venv python 跑 `weekly-update.py`
- 为什么要 systemd worker:`hermes update` 会重启 gateway;若不脱离 gateway cgroup,管道第一步就杀死自己(ADR 0006)
- 升级顺序(失败即 abort 剩余步骤,ADR 0006):
  1. hermes — `hermes update`(升级前备份到 `~/.hermes/backups/pre-hermes-upgrade-<ts>/`,保留 4 份)
  2. category_dirs — 校验 skill 分类同步(ADR 0005,只观察不驱动)
  3. rustc — `rustup update`
  4. codex / claude / openclaw — `npm install -g <pkg>@latest`
  5. opencode — `bun add -g --latest opencode-ai`
  6. pi — hermes node 的 npm 装 `@earendil-works/pi-coding-agent@latest`
  7. npm 全局包 — `npm update -g`(skip.txt 除外)
  8. bun 全局包 — `bun add -g --latest`(skip.txt 除外)
  9. uv tools — `uv tool upgrade --all`
   10. yazi / herdr — GitHub 预编译 release,临时目录下载→校验(ELF/zip)→原子替换(herdr 首次安装见 Stage 3)
  11. `/root/.agents/skills/` — `git pull --rebase --autostash`
- 产物:`~/.hermes/cache/weekly-update/<ts>-<pid>-<hex>/`(pre.json / post.json / digest.md / feishu-payload.json),保留 8 份
- 跳过清单:`~/.hermes/scripts/skip.txt`(apt / dpkg / pwsh / brew / skills / pip / node)
- 验证:`tests/test_single_weekly_update_cron.py`(单一 cron、hermes 首步、部署字节一致)+ `tests/test-weekly-update-wrapper.sh`(transient worker 脱离 cgroup)

### weekly-apt-security-watch — 系统安全更新巡检

- 调度:`0 8 * * 1`(周一 08:00 UTC = 周一 16:00 东八区),agent 模式(ask-matt),deliver=feishu
- 脚本:`~/.hermes/scripts/version-watch/apt-security.sh`,只读本地 `/var/lib/apt/lists` 元数据,输出单行 JSON
- **绝不**执行 `apt upgrade / install`,只报告;元数据超 7 天未刷新时提示先 `sudo apt update`

> 设计依据:`docs/adr/0001..0006`;运行时文件以 `scripts/` 为唯一版本源,部署到 `~/.hermes/scripts/` 需字节一致(test 强制)。
