# Adapter: WorkBuddy (腾讯云 · 桌面智能体工作台)

WorkBuddy 内置 **CodeBuddy Code CLI**（Claude Code 同款形态），自带完整 MCP 客户端管理——这是四个目标平台里适配最顺的之一（2026-09-21 实测通过）。

| Spec concept | WorkBuddy mapping |
|---|---|
| Stage 3 worker | CodeBuddy Agent 逐对象处理（串行），或对话分批 |
| 文件读写 | 桌面文件系统原生访问（D:\ 等任意路径） |
| MCP 工具 | `codebuddy mcp add` 注册 widehive server（已实测 Connected + 端到端核验） |
| 编排规范 | 自定义智能体提示词（见 Trae 适配的精简规范，通用） |
| 合并/校验 | widehive MCP 的 `merge_results` 工具，或直接跑 `scripts/merge_results.py` |
| Scheduling | 暂无 cron — 手动触发 |

## 配置步骤（实测记录）

1. **注册 widehive MCP server**（user 作用域，全局可用）：

   ```powershell
   node "<WorkBuddy>\resources\app.asar.unpacked\cli\dist\codebuddy.js" mcp add --scope user widehive -- python "D:\pythonproject\skill\WideHive\mcp\server.py"
   ```

   或在 WorkBuddy 的 MCP 设置界面等价操作。注册后健康检查自动运行（Connected ✓）。配置写入 `C:\Users\<user>\.codebuddy\mcp.json`。

2. **验证**：`codebuddy mcp list` → widehive: Connected；或端到端：

   ```powershell
   codebuddy -p "调用 widehive MCP 的 merge_results 工具，run_dir 为 <run_dir>，告诉我 verdict" --allowedTools "mcp__widehive__merge_results"
   ```

3. WorkBuddy GUI 的对话/智能体同样可调用（共享 CodeBuddy 账号与 MCP 配置；以 GUI 内实测为准）。

## 实测记录（2026-09-21）

- MCP 注册：✅ Connected（健康检查自动通过）
- 端到端：✅ Agent 正确核验 WideHive 产物（verdict PASS 4/4），并精准指出数据时点与三处媒体口径差异（discrepancy_notes 机制生效）
- 备注：`-p` 非交互模式下 Agent 选择了读文件而非实时调 MCP 工具（权限/命名匹配原因）；交互模式下可弹权限确认，实时调用无障碍

## 限制

- 调度：无 cron — 手动触发
- 多 Agent 并行：WorkBuddy 宣传支持多 Agents 并行，WideHive 场景下的并行度待 GUI 实测确认

## GUI 实测记录（2026-09-21）

| 测试 | 结果 |
|---|---|
| 基础三能力（读文件/联网/写盘） | ✅ 全通过 |
| MCP 工具可见性（GUI） | ❌ GUI Agent 不可见 CLI 注册的 MCP（CLI 侧 Connected）——排查方向：重启 WorkBuddy / GUI 设置内 MCP 开关 / 版本支持 |
| 编排实战（3 仓库调研） | ✅ **原生跑通**：逐仓库落盘 JSON + 主动产出对比汇总，全部数据来自 GitHub REST API 一手来源 |
| 数据质量交叉验证 | ✅ 与 09-16 基线对比，star 变化量在合理区间，零编造痕迹 |

**适配结论：A- 档（双轨形态）**——GUI 侧核心流程原生可用（无需 MCP 即可跑通 WideHive 流程），CLI 侧 MCP 工具已注册可用。MCP 在 GUI 不可见的排查：① 重启 WorkBuddy；② GUI 设置内查找 MCP 开关；③ 若确认 GUI 不支持挂载，接受双轨形态（GUI 走 prompt 流程，CLI/脚本侧走 MCP 工具校验）。