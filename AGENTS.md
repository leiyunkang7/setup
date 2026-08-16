# AGENTS

本仓库的 agent 全局规则,由 `SETUP.md` Stage 5 引用,写入 hermes / openclaw / claude / opencode / codex / pi 这 6 个 agent 的全局配置。

<!-- SETUP_GLOBAL_RULES_START -->
1. **第一性原理**:解决问题、修 BUG、设计架构或方案时,从第一性原理出发。
2. **对抗性审查**:相对复杂的任务完成后,开启多 Agent 对抗性审查。
3. **网络排查**:遇到网络问题,先排查系统代理。
4. **脚本栈**:默认 bun + ts。
5. **写入规则**:时间默认使用东八区(UTC+8),文本默认使用 UTF-8 编码。
<!-- SETUP_GLOBAL_RULES_END -->
