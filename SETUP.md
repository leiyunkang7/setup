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
| 3  | Agent(6 个)+ 插件             | ⏸ |
| 4  | MCP + 模型 + CLI 鉴权         | ⏸ |
| 5  | 全局规则(写入所有 agent)      | ⏸ |
| 6  | 定时更新软件(自动维护)        | —  |

---

## Stage 1 — 运行时 ⏸

**完成准则**:`rustc --version`、`bun --version`、`node --version` 三条命令都能输出。

- rust:https://rustup.rs
- bun:https://bun.sh
- nodejs:https://nodejs.org

⏸ 等三条命令都返回版本号,进入 Stage 2。

---

## Stage 2 — Shell 与默认配置 ⏸

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

## Stage 5 — 全局规则 ⏸

**完成准则**:hermes / openclaw / claude / opencode / codex / pi 这 6 个 agent 的全局配置文件都包含以下 5 条规则。

**合并策略**:不覆盖现有配置,优先复用现有条目;如有重复则跳过。

写入 6 个 agent 的全局配置:

1. **第一性原理**:解决问题、修 BUG、设计架构或方案时,从第一性原理出发。
2. **对抗性审查**:相对复杂的任务完成后,开启多 Agent 对抗性审查。
3. **代理优先**:遇到网络问题,先排查系统代理。
4. **脚本栈**:默认 bun + ts。
5. **写入规则**:时间默认使用东八区（UTC+8）,文本默认使用 UTF-8 编码。

⏸ 等 6 个 agent 的配置都验证通过。

---

## Stage 6 — 定时更新软件 ⏸

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
  10. yazi / herdr — GitHub 预编译 release,临时目录下载→校验(ELF/zip)→原子替换
  11. `/root/.agents/skills/` — `git pull --rebase --autostash`
- 产物:`~/.hermes/cache/weekly-update/<ts>-<pid>-<hex>/`(pre.json / post.json / digest.md / feishu-payload.json),保留 8 份
- 跳过清单:`~/.hermes/scripts/skip.txt`(apt / dpkg / pwsh / brew / skills / pip / node)
- 验证:`tests/test_single_weekly_update_cron.py`(单一 cron、hermes 首步、部署字节一致)+ `tests/test-weekly-update-wrapper.sh`(transient worker 脱离 cgroup)

### weekly-apt-security-watch — 系统安全更新巡检

- 调度:`0 8 * * 1`(周一 08:00 UTC = 周一 16:00 东八区),agent 模式(ask-matt),deliver=feishu
- 脚本:`~/.hermes/scripts/version-watch/apt-security.sh`,只读本地 `/var/lib/apt/lists` 元数据,输出单行 JSON
- **绝不**执行 `apt upgrade / install`,只报告;元数据超 7 天未刷新时提示先 `sudo apt update`

> 设计依据:`docs/adr/0001..0006`;运行时文件以 `scripts/` 为唯一版本源,部署到 `~/.hermes/scripts/` 需字节一致(test 强制)。
