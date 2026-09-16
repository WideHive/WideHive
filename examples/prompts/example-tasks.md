# Example task prompts

Copy-paste starting points. Replace the bracketed parts. Dispatch language
follows whatever language you talk to your agent in.

---

## 1. Minimal smoke test — tech, explicit list (3 objects)

**English:**

> Use WideHive to build a comparison table for these 3 GitHub repos:
> langchain-ai/langgraph, crewAIInc/crewAI, microsoft/autogen.
> Fields: name, owner, positioning, latest_version, stars, license, url.

**中文：**

> 用 WideHive 给这三个 GitHub 仓库做对比表：
> langchain-ai/langgraph, crewAIInc/crewAI, microsoft/autogen。
> 字段：name, owner, positioning, latest_version, stars, license, url。

A good first run: fast, verifiable, and shows the checkpoint/resume behavior
(archived in `examples/smoke-test-3repos/`).

## 2. Financial — explicit list (30 objects)

**English:**

> Use WideHive to compare the latest annual reports of these 30 companies:
> <company list>.
> Focus on revenue, net profit, gross margin, YoY growth, key segments, and
> major risks. Deliverable: a CSV table first, then a compact comparison report
> highlighting outliers.

**中文：**

> 用 WideHive 对比这 30 家公司的最新年报：<公司清单>。
> 重点关注营收、净利润、毛利率、同比增速、关键业务线和主要风险。
> 产出：先给 CSV 总表，再给一份突出异常值的精简对比报告。

## 3. Academic — topic mode (enumerate first, then fan out)

**English:**

> Use WideHive to survey recent papers (2024–2026) on multi-agent
> evaluation benchmarks. I only have the topic — first enumerate the candidate
> papers with sources and let me confirm the list, then read each paper:
> research question, method, findings, limitations. Deliverable: a single-page
> review where every summary links back to the paper.

**中文：**

> 用 WideHive 综述 2024–2026 年多智能体评测基准方向的论文。我只有主题——
> 先枚举候选论文清单（附来源）给我确认，确认后逐篇阅读：研究问题、方法、结论、局限。
> 产出：单页综述，每条摘要都可点回原文。

## 4. Custom fields

Override the default template inline:

> Use WideHive on these 50 SaaS products. Fields: name, pricing_model,
> free_tier, api_access, soc2, data_residency, url. Deliverable: CSV.
