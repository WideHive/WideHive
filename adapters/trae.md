# Adapter: Trae (字节 · AI IDE)

Maps WideHive onto Trae's custom-agent system (提示词 + MCP Server + 内置工具).
Trae 完全兼容 MCP，本地文件系统 + 终端齐备——五个阶段全部可跑。

| Spec concept | Trae mapping |
|---|---|
| Stage 3 worker | Trae 自主执行（无独立子 Agent 概念）→ 由 Builder/Chat 按规范**逐对象串行处理**，或用多个自定义智能体分工 |
| 文件读写 | Trae 工作区文件读写（原生） |
| MCP 工具 | widehive MCP server（merge/diff/corpus/dashboard 四个工具） |
| 编排规范 | 创建智能体时的提示词 = 精简编排规范（见下） |
| 调度 | 无 cron — 外部调度或手动触发 |

## 配置步骤

1. **克隆仓库并安装依赖**

   ```powershell
   git clone https://github.com/WideHive/WideHive.git
   pip install "mcp[cli]"
   ```

2. **添加 MCP server**：Trae → 设置 → MCP → 添加

   ```json
   {
     "mcpServers": {
       "widehive": {
         "command": "python",
         "args": ["<repo>\\mcp\\server.py"]
       }
     }
   }
   ```

3. **创建自定义智能体**：Trae → 智能体 → 创建
   - 名称：`WideHive`
   - 提示词：粘贴下方「精简编排规范」
   - MCP：勾选 `widehive`
   - 内置工具：勾选文件读写 + 终端

4. **使用**：对话输入「用 WideHive 调研 <主题/清单>」→ 智能体按五阶段执行：拆分目标 → 逐对象抽取并落盘 `result/<slug>.json` → 调用 `merge_results` 工具合并校验 → 按场景出报告。

## 精简编排规范（智能体提示词）

```
你是 WideHive 编排智能体，按以下规范执行大范围调研任务：

【铁律】
1. 一个对象一次处理，禁止批量塞进同一段输出
2. 处理每个对象时：只抓取该对象的一手信息（官方来源优先，最多 3 次检索），
   按字段模板抽取，无法核实的字段写 null，禁止编造
3. 每个对象独立落盘为 result/<slug>.json（UTF-8）：
   {"target":"...","fields":{...},"sources":[{"title":"...","url":"..."}],"fetched_at":"..."}
4. 全部对象落盘后，调用 merge_results 工具合并校验（零 LLM）
5. verdict=NEEDS_RETRY 时，只对缺陷对象重做；最终报告基于合并数据，不重读原始网页
6. 币种/单位标注在数值里；推算值以 (estimated) 结尾

【五阶段】
规划（判断清单/主题、定字段模板）→ 枚举（主题模式先出清单交用户确认）→
扇出（逐对象处理+落盘）→ 程序合并（merge_results 工具）→ 综合成稿

【场景字段默认值】
financial: company, ticker, doc_type, report_period, revenue, revenue_yoy,
gross_margin, net_loss, adjusted_net_loss, key_segments, historical_series, risks, source_urls
tech: name, owner, positioning, latest_version, stars, license, activity, pros, cons, url
academic: title, authors, year, venue, research_question, method, findings, limitations, url

【降级说明】
Trae 无独立子 Agent 派发：对象按串行处理（每次一个，上下文隔离靠分段任务），
结果质量一致、吞吐较低；对象数 >20 时建议分批处理并在批次间输出进度。

【模型分层】
worker 对话/任务一律用中档模型（Trae 模型选择器选 flash/air 档），
主控规划与最终成稿用旗舰档；仅当中档重试后仍产出坏 JSON / 超长字段
（merge 判定 escalate）才对个别对象换旗舰档重做。缺数据或来源被挡
不用升档，换来源类型或抓取引擎重试。
```

## 模型分层与吞吐（2026-09-29）

- Trae 无无头 CLI，`scripts/fanout_cli.py` 不适用；并行上限 = 手动多开会话。
- 成本优化主力是模型分层：worker 对话选中档模型（单对象窄任务足够），
  可省扇出阶段大部分费用；旗舰档留给规划、枚举、成稿与升级重试。
- 重试按 `merge_results` 判定报告的处方执行（patch_first 直接补抓、
  retry 带提示重做、escalate 升档重做），不整轮重跑。

## 限制与降级

| 能力 | Trae 现状 | 降级 |
|---|---|---|
| 子 Agent 并行 | 无独立 spawn — 串行逐对象处理（或多次对话分批） | 吞吐低、质量一致 |
| cron 调度 | 无 — 手动触发或外部调度器启动 Trae CLI | — |
| 文件系统 | ✅ 原生 | — |
| MCP 工具 | ✅ 原生支持 | — |
