# Changelog

All notable changes to this project are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.6.0] - 2026-09-29

### Added

- **Thin API worker 驱动器**（`skill/scripts/fanout_api.py`）：无需任何 agent
  平台——脚本自抓页面（HTML 优先阶梯，可选 Tavily/Bocha 搜索）→ 调任意
  OpenAI 兼容 API 纯抽取 → 脚本侧构建 sources（来源可信度由构造保证）。与
  fanout_cli.py 同一套断点/处方/升级/日志契约；所有失败路径落盘为披露记录。
  执行器分层成立：thin 为默认，fetch_failed/invalid_output 对象按处方路由
  到 agent worker 阶梯；merge_results.py 将 `worker_error: invalid_output`
  判定为能力缺陷（escalate）。
- **100 仓库 benchmark 预注册方案**（`benchmarks/100repos/PLAN.md`）：清单选型
  规则（10 类目 × GitHub Search top-10，可复现）、双基线对照组设计（旗舰/flash
  单上下文，分离编排效应与模型效应）、同日地面真值程序化评分（coverage /
  accuracy / fabrication 分计）、token 账本与预注册通过线。
- **并行 CLI 扇出驱动器**（`skill/scripts/fanout_cli.py`）：为无子代理派发能力的
  无头 CLI 平台（WorkBuddy/CodeBuddy、Claude Code、Codex CLI）提供进程级并行
  扇出——单对象单 worker、并发上限、断点续跑（`result/` checkpoint）、
  stdout-JSON 兜底落盘（`patched_by: stdout_capture`）、逐 worker 结果日志
  `fanout_log.jsonl`（可作耗时/成本基线）。Windows 路径与命令行解析兼容。
- **模型分层落地**：`plan.json` 新增 `models: {"worker": 中档, "escalate_to":
  旗舰}`——worker 默认中档，旗舰档只留给升级对象（合并判定 escalate、
  中档跑满重试轮次、或计划预标难点的对象）。

### Changed

- **重试带处方**（`skill/scripts/merge_results.py`）：判定报告新增
  `retry_hint` / `escalate` / `patchable` 逐对象字段与 `retry_queue`
  （`patch_first` / `retry` / `escalate`）分组；重试从"整轮重跑"改为按处方
  定向修复——确定性缺字段直接补抓（patch_first），能力型缺陷（坏 JSON、
  超长）才升档重试，来源被挡走降级阶梯不升档。
- **SKILL.md**：Stage 3 写入模型分层默认策略与 fanout_cli 用法；重试阶梯
  按处方重排（patch_first 提前）；成本纪律改为"模型分层是默认而非可选项"。
- **Tech-selection 场景包**（`scenarios/tech-selection.md`）：仓库/库/开发工具
  选型矩阵——核心字段 + `maintenance_status` 枚举 + HTML 优先的来源阶梯（规避
  GitHub API 每 IP 共享限流坑）+ 许可证风险显式化 + watch 配置示例；冒烟级验证
  （`examples/smoke-test-3repos/`，3 仓库端到端 PASS）。已注册为 MCP resource。
- **adapters**：workbuddy.md 新增 fanout_cli 并行扇出 + 模型分层章节
  （CodeBuddy headless v2.147.0 旗标级验证，含登录注意事项）；trae.md 新增
  模型分层与吞吐说明；adapters/README.md 能力矩阵补 WorkBuddy 列与
  并行/分层两行。

## [1.4.0] - 2026-09-16

### Added

- **Multimodal objects**: the fetch ladder extends to video (transcript-first),
  audio, and images; unsupported modalities are disclosed via
  `unsupported_modality`, never silently dropped.
- **Tabular intake & write-back**: target lists from CSV/TSV/spreadsheets,
  results appended back with `wh_*`-prefixed columns; composes with watch mode
  for monitoring a living list.
- **Harness adapters** (`adapters/`): per-harness mapping docs — OpenClaw
  (canonical), Claude Code, Codex CLI — plus a capability matrix.

## [1.5.0] - 2026-09-21

### Added

- **widehive-mcp server**（mcp/server.py）：四个零 LLM 工具（merge/diff/corpus/dashboard）封装为 MCP tools，编排规范与场景包作为 resources/prompts；兼容 mcp 1.x/2.x。
- **Trae 适配**（dapters/trae.md）：自定义智能体配置指南 + 精简编排规范提示词。

## [1.3.0] - 2026-09-16

### Added

- **Corpus (knowledge base across runs)**: `scripts/build_corpus.py` consolidates
  finished runs into `corpus.jsonl` + an index; query discipline added to the
  spec (answer from the corpus first, cite run + fetch date, targeted re-runs
  for gaps — never re-fan-out to answer an already-researched question).
- **Interactive dashboard**: `scripts/build_dashboard.py` turns merged.json into
  a self-contained HTML dashboard (search / sort / drill-down with sources /
  numeric bar charts), no external dependencies.

## [1.1.0] - 2026-09-16

### Added

- **Watch mode (scheduled monitoring)**: set `mode: "watch"` plus a `watch`
  block in `plan.json`; new `scripts/diff_results.py` diffs a current run
  against a baseline (zero LLM), and the orchestrator re-fans-out **only**
  new/changed objects, carrying unchanged results forward. Idle scheduled runs
  cost ≈ 0.
- **Scenario packs** (`scenarios/`): prompt-only domain configurations. First
  pack: `financial-filings` — prospectus/annual-report extraction with currency
  discipline, IFRS-vs-adjusted separation, and a validated report layout
  (survived a real 4-object run).
- **Model tiering guidance**: strong model for enumerate/synthesize; default or
  cheaper model for workers.
- **Retry playbook**: ordered fallback ladder (retry → alternate source →
  alternate fetch engine → field-level fallback → disclose skipped).

## [1.0.0] - 2026-09-16

### Added

- Five-stage orchestration spec: Plan → Enumerate → Fan out → Merge → Synthesize.
- `scripts/merge_results.py`: zero-LLM programmatic merge with field / URL /
  length validation and a JSON verdict report (`PASS` / `NEEDS_RETRY`).
- Checkpoint-resume semantics: one `result/<slug>.json` per object; interrupted
  runs resume by only redoing missing objects.
- Default field templates for three scenarios: `financial`, `academic`, `tech`
  (all overridable via `plan.json` or per-run instructions).
- Backend fallback chain for web fetching: dedicated web-open tools (e.g.
  AutoGLM open-link) → platform built-in fetch → explicit `fetch_failed` marker
  (objects are never silently dropped).
- Retry queue with bounded rounds plus an orchestrator fallback rule for
  infrastructure-type worker failures.
- Worked example: `examples/smoke-test-3repos/` — an archived real run over
  three GitHub repositories with `verdict: PASS`.
