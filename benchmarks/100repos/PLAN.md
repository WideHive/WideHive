# Benchmark: 100 仓库选型扫描（执行方案 v1）

> 预注册文档：本文件与 `targets.json` 在**开跑之前**提交入库。之后不改清单、
> 不改字段、不改评分规则；跑了什么就报什么——包括失败。这是本 benchmark
> 唯一的可信度来源。

## 目的

一次运行同时回答三个问题：

1. WideHive 能否在真实规模（100 对象）下做到 100/100 覆盖、零编造
   （tech-selection 场景包的规模级验证）；
2. 相对单上下文基线，编排带来多大的覆盖/质量差（对照组）；
3. 宽调研的真实成本与耗时（模型分层下的 token 账本）。

## 一、清单选型（可复现，预注册）

**任务叙事**：对 AI 开发者工具生态做一次选型扫描——WideHive 调研它自己
所在的生态，受众与分发天然重合。

**选型规则**（GitHub Search API，查询串原样记录）：

- 10 个类目 × 每类目 stars 降序前 10：agent 框架、LLM 推理引擎、向量数据库、
  RAG 框架、微调/训练、评测、guardrails/安全、MCP 生态、提示工程库、
  多模态/语音；
- 每类目查询模板：`topic:<t> stars:>2000 sort:stars`（topic 无 10 个候选时
  放宽为 `stars:>1000` 并记录）；类目间去重（按 `owner/repo`），缺额从
  排名顺延补足；
- 过程脚本 `select.py` 输出 `targets.json` 并附带：每条目的来源查询串、
  快照日期。快照日期即清单的锚定日期，之后 star 数自然漂移属预期，
  由同日地面真值规则处理（见下）。

**刻意不做的事**：不剔除 stale/archived 仓库（顶部明星仓库里也有归档者，
自然分布才能真实检验 `maintenance_status` 枚举）；不手工增删任何条目。

## 二、字段模板（= tech-selection 包核心字段）

```
name, owner, repo_url, language, latest_version, latest_release_date,
license_spdx, stars, last_commit_date, maintenance_status, positioning
```

- 深度字段（docs_url / open_issues / cve_notes）**不进**本次 run——字段数
  与成本、null 率正相关的结论本身就是要控的变量；
- `positioning` 取项目自述（README/docs 一句话），dispatch 语言为中文，
  值内可保留英文原文；
- `plan.json` 模型分层：`{"worker": "glm-5.3-flash", "escalate_to": "glm-5.3"}`
  （本机 CodeBuddy 已验证的档位）。

## 三、对照组设计（双基线）

| 配置 | 编排 | 模型 | 回答的问题 |
|---|---|---|---|
| **wide**（主实验） | WideHive 扇出，`fanout_cli.py` 并发 4→8 | worker=flash，主控=旗舰 | 完整方案的表现 |
| **baseline-A** | 无——单会话顺序处理，同一份 targets.json | 旗舰 glm-5.3 | 最好的单上下文能做到多少 |
| **baseline-B** | 同上 | flash | 把"编排效应"从"模型效应"里分离出来 |

- 三个配置使用**同一份 targets.json、同一字段模板、同一评分脚本**；
- 基线提示词与 worker 模板同源（同一字段定义与 null 纪律），唯一差别是
  单上下文、无扇出、无合并校验；
- 基线允许自然停摆（预期在 12–20 行后质量衰减/停止，与 codex_wide_research
  的公开结论同型），停摆即记录，不催促不重试；
- 披露义务：wide 的 worker 是 flash、基线是旗舰——这是产品主张本身
  （编排让便宜模型达标），报告中必须显式说明，baseline-B 就是为此存在。

## 四、评分（程序化，不靠人眼）

**地面真值**：开跑当日用 GitHub API 批量拉取同字段真值
（`repos/{owner}/{repo}` + `releases/latest`，200 次调用；有 token 则
5k/h 一次跑完，无 token 按 60/h 分散到前一日预拉并记录快照时间）。
生成 `groundtruth.json`，与 run 结果**同日**比对。

| 字段 | 评分方式 |
|---|---|
| stars / last_commit_date / maintenance_status | 与真值精确比对（同日规则） |
| latest_version / latest_release_date | 与真值精确比对；`(pre)` 标记视为一致 |
| license_spdx / language / repo_url | 精确比对 |
| positioning | 不进程序评分；抽检 20 条与官方 description 的人工一致性 |
| null 的处理 | scoreable 字段填 null 记为"未覆盖"，不记为错误——覆盖与正确分开计分 |

**指标定义**：

- `coverage` = 全部核心字段非 null 的对象数 / 100
- `accuracy` = 有值字段与真值一致的比例（分母 = 有值字段数）
- `fabrication` = 有值但与真值矛盾的条目数（这个数字必须为 0 才配讲
  "零编造"，否则如实报告）
- `wall_time` / `tokens`（`fanout_log.jsonl` 逐 worker 记录）/ `成本`

**预注册的通过线**：coverage ≥ 95% 且 accuracy ≥ 95% 且 fabrication = 0
→ 发布；accuracy < 90% → 先归因（来源阶梯？字段歧义？）修 spec，重跑，
**两批结果都公开**。跑砸了照发——诚实缺口是这个项目品牌的一部分。

## 五、成本估算（token 账本，价格留白待填）

数量估算（定价因 CodeBuddy 订阅/直充而异，先记量、后填价）：

| 配置 | 输入 token（估） | 输出 token（估） | 依据 |
|---|---|---|---|
| wide：100 worker | 1.0–1.7M | 40–50k | 每 worker ≈ 2k（系统+提示）+ 2–3 页抓取 × 3–6k；输出 ≤400 词 |
| wide：重试轮（预估 5–15% 缺陷） | +100–250k | +5–8k | 带处方定向重试，只补缺陷 |
| wide：主控旗舰（规划/抽检/成稿） | 150–300k | 20–30k | 不重读原始网页，只读 merged.json |
| 合并/评分/地面真值 | **0** | **0** | 全程序化 |
| baseline-A（旗舰，停摆前） | 150–400k | 20–40k | 抓 12–20 页 + 反复重写表格 |
| baseline-B（flash，停摆前） | 150–400k | 20–40k | 同上，单价更低 |

填价表（执行时从计费页抄录，双币种标注）：

| 档位 | 输入价/M tokens | 输出价/M tokens | wide 总成本 | 三配置总成本 |
|---|---|---|---|---|
| flash | ______ | ______ | ______ | ______ |
| 旗舰 | ______ | ______ | ______ | ______ |

若走 CodeBuddy 订阅额度：边际成本记 ≈0，但**token 量照常披露**——量才是
可迁移的证据，价是每家不同的。

**耗时估算**：并发 4 ≈ 25 波 × 2–4 分钟 ≈ 50–100 分钟；并发 8（探测通过后）
≈ 25–50 分钟。两个基线各 ≈ 30–60 分钟自然停摆。地面真值（有 token）
≈ 5 分钟。

## 六、执行清单（四天节奏）

1. **D1**：登录 CodeBuddy CLI → `select.py` 出清单 → 人工过目无脏数据 →
   提交 PLAN + targets.json（预注册完成）→ 地面真值预拉（若需分摊配额）；
2. **D2**：10 仓库冒烟（验证 fanout_cli + 场景包 + 评分脚本全链路）→
   修 prompt 问题 → 提交冒烟 run；
3. **D3**：并发探测 2→4→8 → wide 全量 100 → 当日拉同日真值 →
   baseline-A / baseline-B（同日，防漂移）；
4. **D4**：`score.py` 出分 → 定位差异（如有）→ 按预注册通过线决定发布
   或修复重跑 → 成稿（README 首屏数字 + 中英文章）。

## 七、风险与预案

| 风险 | 预案 |
|---|---|
| CodeBuddy 无头模式未登录 | D1 第一件事：CLI 内 `/login` 一次 |
| GitHub API 限流风暴 | worker 走 HTML 优先阶梯（pack 已定义）；真值拉取用 token 或前日分摊 |
| 归档/停摆样本不足 | 接受自然分布，不为枚举覆盖率硬造清单 |
| flash 在某类字段系统性出错 | 升级处方自然生效（escalate_to 旗舰）；错误率按预注册规则如实报告 |
| 快照漂移（跨日重跑/重试） | 同日规则；重试轮与真值拉取必须落在同一自然日内 |
| 结果好得可疑 | 抽检 20 条人工复核 + 公开全部原始 run 目录与日志供第三方复算 |

## 交付物

```
benchmarks/100repos/
├── PLAN.md                 # 本文件（预注册）
├── select.py               # 清单生成（查询串内嵌）
├── targets.json            # 100 对象（提交后再跑）
├── groundtruth.py / groundtruth.json
├── score.py                # 程序化评分
├── run-wide/               # 完整 run 目录（targets/plan/result/merged/log）
├── run-baseline-a/  run-baseline-b/
└── REPORT.md               # 数字 + 两批结果（如重跑）+ 全部披露
```
