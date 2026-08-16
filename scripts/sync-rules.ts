#!/usr/bin/env bun
/**
 * sync-rules.ts — 把 repo 根 AGENTS.md 的 SETUP 全局规则块同步到 6 个 agent 的全局配置。
 *
 * 规则唯一源:repo 根 AGENTS.md 中 `<!-- SETUP_GLOBAL_RULES_START -->` 与
 * `<!-- SETUP_GLOBAL_RULES_END -->` 之间的内容。以后改规则只改 AGENTS.md,再重跑本脚本。
 *
 * 行为:
 *   - 已有标记块的文件:只替换块内内容,其余部分不动
 *   - 没有标记块的文件:在文件末尾追加整个块(先补换行)
 *   - 写入前把原文件备份到 ~/.setup-backups/<ts>/
 *
 * 用法:
 *   bun run scripts/sync-rules.ts                       # dry-run:打印 digest,不写任何文件(默认)
 *   bun run scripts/sync-rules.ts --apply               # 实际写入
 *   bun run scripts/sync-rules.ts --agent-file claude=/path/to/CLAUDE.md   # 覆盖某 agent 的配置路径
 *   bun run scripts/sync-rules.ts --help
 *
 * Windows 下各 agent 配置路径不同(如 %USERPROFILE%\.claude\CLAUDE.md),用 --agent-file 指定;
 * 支持 --agent-file name=path 与 --agent-file=name=path 两种写法,可重复传入。
 */
import { existsSync, mkdirSync, copyFileSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, basename, join } from "node:path";
import { homedir } from "node:os";

const START = "<!-- SETUP_GLOBAL_RULES_START -->";
const END = "<!-- SETUP_GLOBAL_RULES_END -->";
const REPO_ROOT = dirname(dirname(new URL(import.meta.url).pathname));

const DEFAULT_FILES: Record<string, string> = {
  hermes: join(homedir(), ".hermes", "SOUL.md"),
  openclaw: join(homedir(), ".openclaw", "workspace", "AGENTS.md"),
  claude: join(homedir(), ".claude", "CLAUDE.md"),
  opencode: join(homedir(), ".config", "opencode", "AGENTS.md"),
  codex: join(homedir(), ".codex", "AGENTS.md"),
  pi: join(homedir(), ".pi", "agent", "AGENTS.md"),
};

function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

type Args = { apply: boolean; files: Record<string, string>; help: boolean };

function parseArgs(argv: string[]): Args {
  const args: Args = { apply: false, files: { ...DEFAULT_FILES }, help: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--apply") args.apply = true;
    else if (a === "--help" || a === "-h") args.help = true;
    else if (a === "--agent-file") {
      const kv = argv[++i];
      if (!kv || !kv.includes("=")) throw new Error("--agent-file 需要 <name>=<path>");
      const idx = kv.indexOf("=");
      args.files[kv.slice(0, idx)] = kv.slice(idx + 1);
    } else if (a.startsWith("--agent-file=")) {
      const kv = a.slice("--agent-file=".length);
      const idx = kv.indexOf("=");
      args.files[kv.slice(0, idx)] = kv.slice(idx + 1);
    } else {
      throw new Error(`未知参数: ${a}(--help 查看用法)`);
    }
  }
  return args;
}

function extractBlock(src: string): string {
  const re = new RegExp(`${esc(START)}\\s*([\\s\\S]*?)\\s*${esc(END)}`);
  const m = src.match(re);
  if (!m) throw new Error(`AGENTS.md 缺少 ${START} 标记块,请先在 repo 根 AGENTS.md 包上标记`);
  return m[1].trim();
}

type Result = {
  name: string;
  path: string;
  status: "up-to-date" | "update-pending" | "missing" | "error";
  detail?: string;
};

function syncTarget(
  name: string,
  path: string,
  block: string,
  apply: boolean,
  backupDir: string,
): Result {
  if (!existsSync(path)) return { name, path, status: "missing" };
  let orig: string;
  try {
    orig = readFileSync(path, "utf8");
  } catch (e) {
    return { name, path, status: "error", detail: String(e) };
  }

  const blockRe = new RegExp(`${esc(START)}\\s*[\\s\\S]*?\\s*${esc(END)}`);
  const innerRe = new RegExp(`${esc(START)}\\s*([\\s\\S]*?)\\s*${esc(END)}`);
  const canonical = `${START}\n${block}\n${END}`;

  if (blockRe.test(orig)) {
    const inner = orig.match(innerRe)![1].trim();
    if (inner === block) return { name, path, status: "up-to-date" };
    if (!apply) return { name, path, status: "update-pending", detail: "替换标记块内内容" };
    try {
      copyFileSync(path, join(backupDir, `${basename(path)}.${name}.bak`));
      writeFileSync(path, orig.replace(blockRe, canonical), "utf8");
    } catch (e) {
      return { name, path, status: "error", detail: String(e) };
    }
    return { name, path, status: "update-pending", detail: "已替换标记块内内容(已备份)" };
  }

  if (!apply) return { name, path, status: "update-pending", detail: "文件末尾追加标记块" };
  try {
    copyFileSync(path, join(backupDir, `${basename(path)}.${name}.bak`));
    const suffix = orig.endsWith("\n") ? "" : "\n";
    writeFileSync(path, orig + suffix + canonical + "\n", "utf8");
  } catch (e) {
    return { name, path, status: "error", detail: String(e) };
  }
  return { name, path, status: "update-pending", detail: "已追加标记块(已备份)" };
}

const args = parseArgs(process.argv.slice(2));
if (args.help) {
  console.log(`用法:
  bun run scripts/sync-rules.ts                dry-run:打印 digest,不写文件
  bun run scripts/sync-rules.ts --apply        实际写入(每个文件先备份到 ~/.setup-backups/<ts>/)
  --agent-file <name>=<path>                   覆盖某 agent 配置路径(可重复),Windows 必用
规则源:repo 根 AGENTS.md 的 SETUP_GLOBAL_RULES_START/END 标记块`);
  process.exit(0);
}

const block = extractBlock(readFileSync(join(REPO_ROOT, "AGENTS.md"), "utf8"));
const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const backupDir = join(homedir(), ".setup-backups", ts);
if (args.apply) mkdirSync(backupDir, { recursive: true });

console.log(
  args.apply
    ? `[apply] 写入模式,备份目录: ${backupDir}`
    : "[dry-run] 未写任何文件;加 --apply 生效",
);

let up = 0;
let pend = 0;
let miss = 0;
let errs = 0;
for (const [name, path] of Object.entries(args.files)) {
  const r = syncTarget(name, path, block, args.apply, backupDir);
  const label = r.status === "update-pending" && args.apply ? "UPDATED      " : r.status.padEnd(14);
  const detail = r.detail ? `  (${r.detail})` : "";
  console.log(`  ${name.padEnd(10)} ${label} ${r.path}${detail}`);
  if (r.status === "up-to-date") up++;
  else if (r.status === "update-pending") pend++;
  else if (r.status === "missing") miss++;
  else errs++;
}

console.log(
  `\n${Object.keys(args.files).length} 个 agent:${up} up-to-date / ${pend} ${args.apply ? "已更新" : "待更新"} / ${miss} 缺失 / ${errs} 错误`,
);
process.exit(errs + miss > 0 ? 1 : 0);
