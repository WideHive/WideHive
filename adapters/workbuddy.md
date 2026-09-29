# Adapter: WorkBuddy (腾讯云 · 桌面智能体工作台)

WorkBuddy 内置 **CodeBuddy Code CLI**（Claude Code 同款形态），自带完整 MCP 客户端管理——这是四个目标平台里适配最顺的之一（2026-09-21 实测通过）。

| Spec concept | WorkBuddy mapping |
|---|---|
| Stage 3 worker | **首选：`scripts/fanout_cli.py` 并行驱动 CodeBuddy 无头 CLI**（见下）；备选：CodeBuddy Agent 逐对象处理（串行），或对话分批 |
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

## 并行扇出 + 模型分层（fanout_cli.py，2026-09-29 旗标级验证）

CodeBuddy 无头 CLI（`codebuddy-headless.js`，本机版本 2.147.0）支持 `-p` 无头
模式与 `--model` 按 worker 指定模型，使 WideHive 的 P0 双优化（真并行 +
worker 模型降档）可以在 WorkBuddy 上完整落地：

- CLI 路径：`<WorkBuddy>\resources\app.asar.unpacked\cli\dist\codebuddy-headless.js`
  （经 `node` 调用；`fanout_cli.py --cli auto` 会自动探测到它）
- 已验证旗标：`-p`（无头输出）、`--model`（支持档位含 `glm-5.3-flash` /
  `deepseek-v4.1-flash` 等中低档，`glm-5.3` / `deepseek-v4-pro` 等旗舰档）、
  `--permission-mode acceptEdits`（自动接受文件写入）、`--tools`
- ⚠️ 无头模式需要 CLI 侧登录：新 shell 里曾出现 `Authentication required`。
  先跑一次 `node <codebuddy-headless.js>` 进入交互会话 `/login`，或从已登录
  的 GUI 环境启动；登录一次后无头调用复用凭据。

`plan.json` 模型分层示例（中档跑 worker、难点对象升级旗舰）：

```json
{"models": {"worker": "glm-5.3-flash", "escalate_to": "glm-5.3"}}
```

全量扇出（先 dry-run 检查派发计划）：

```powershell
python <skill_dir>\scripts\fanout_cli.py --run-dir <run_dir> --concurrency 4 --dry-run
python <skill_dir>\scripts\fanout_cli.py --run-dir <run_dir> --concurrency 4
```

带处方重试（只重跑缺陷对象，自动注入 retry_hint 并升级 escalate 对象）：

```powershell
python <skill_dir>\scripts\merge_results.py --run-dir <run_dir> > <run_dir>\verdict.json
python <skill_dir>\scripts\fanout_cli.py --run-dir <run_dir> --hints <run_dir>\verdict.json --slugs <retry_queue 各组 slug> --force
```

## 实测记录（2026-09-21）

- MCP 注册：✅ Connected（健康检查自动通过）
- 端到端：✅ Agent 正确核验 WideHive 产物（verdict PASS 4/4），并精准指出数据时点与三处媒体口径差异（discrepancy_notes 机制生效）
- 备注：`-p` 非交互模式下 Agent 选择了读文件而非实时调 MCP 工具（权限/命名匹配原因）；交互模式下可弹权限确认，实时调用无障碍

## 限制

- 调度：无 cron — 手动触发
- 多 Agent 并行：GUI 侧仍为串行；CLI 侧用 `fanout_cli.py` 获得 4–8 并发（2026-09-29 旗标级验证，端到端扇出待登录后首跑确认）

## GUI 实测记录（2026-09-21）

| 测试 | 结果 |
|---|---|
| 基础三能力（读文件/联网/写盘） | ✅ 全通过 |
| MCP 工具可见性（GUI） | ❌ GUI Agent 不可见 CLI 注册的 MCP（CLI 侧 Connected）——排查方向：重启 WorkBuddy / GUI 设置内 MCP 开关 / 版本支持 |
| 编排实战（3 仓库调研） | ✅ **原生跑通**：逐仓库落盘 JSON + 主动产出对比汇总，全部数据来自 GitHub REST API 一手来源 |
| 数据质量交叉验证 | ✅ 与 09-16 基线对比，star 变化量在合理区间，零编造痕迹 |

**适配结论：A- 档（双轨形态）**——GUI 侧核心流程原生可用（无需 MCP 即可跑通 WideHive 流程），CLI 侧 MCP 工具已注册可用。MCP 在 GUI 不可见的排查：① 重启 WorkBuddy；② GUI 设置内查找 MCP 开关；③ 若确认 GUI 不支持挂载，接受双轨形态（GUI 走 prompt 流程，CLI/脚本侧走 MCP 工具校验）。