# WideHive

*把一个问题，交给一整个蜂巢。*

**给 AutoClaw / OpenClaw 智能体装上 WideHive**——把上百个目标对象分发给上百个上下文隔离的子 Agent 并行处理，用程序（而非 LLM）合并结果，按场景产出结构化报告。

<p align="center">
  <img src="assets/architecture.svg" alt="WideHive 五阶段流水线" width="100%">
</p>

## 为什么需要它

LLM 有一个普遍缺陷：当输出占到上下文窗口的 20–50% 时就开始"偷懒"——跳句、缩略、改写。几十上百个对象的调研任务必然撞上这堵墙：模型认真处理前十项，剩下的悄悄糊弄。

WideHive 用分而治之绕开这堵墙：

- **上下文隔离**——每个对象一个独立子 Agent，每个输出天然很短、忠实可靠；
- **程序合并**——用脚本（而不是 LLM）聚合与校验，聚合环节零幻觉；
- **诚实空缺**——子 Agent 查不到的值写 `null` 而不是编造；合并脚本检出缺陷并打回重试队列。

策略思路源自 [Manus Wide Research](https://manus.im/blog/introducing-WideHive)，分治-合并模式经开源项目 [codex_wide_research](https://github.com/grapeot/codex_wide_research) 实证：53 篇博客全文总结零幻觉，而单上下文基线（Deep Research、手工模式）只覆盖 12–20 篇就停滞。

## 快速开始

**在 AutoClaw 中使用（推荐）**：WideHive 已上架 AutoClaw 技能市场（ClawHub）。从市场安装，或直接对你的 AutoClaw 助手说「帮我安装 WideHive」，然后聊天里一句话触发：*「用 WideHive 调研 …」*。

**在其他 OpenClaw 智能体上：**

```bash
# 从 ClawHub 安装：
openclaw skills install widehive

# 或手动：把 skill 目录复制进你的 workspace skills/ 目录
git clone https://github.com/<owner>/WideHive.git
cp -r WideHive/skill <你的workspace>/skills/widehive
```

**使用**——聊天里一句话触发：

```
用 WideHive 对比这 30 家公司的最新年报现金流：<清单>   # 财报场景 → 表格优先

Use WideHive to survey the top AR glasses makers   # 主题模式 →
                                                        # 先枚举清单给你确认，再扇出
```

**接下来会发生什么**：规划 →（主题模式先枚举清单给你确认）→ 分批派发子 Agent（每个对象一个）→ 程序合并校验 → 产出最终报告，并附上全部原始结果供核查。

## 工作原理

| 阶段 | 执行者 | 做什么 |
|---|---|---|
| 1 规划 | 主模型 | 判断输入形态（清单/主题）、确定场景、写 plan.json |
| 2 枚举 | 主模型 + 联网搜索 | 仅主题模式：生成候选清单，交用户确认 |
| 3 扇出 | 子 Agent（默认模型） | 每批约 10 个，每个对象一个窄提示词，逐对象落盘 |
| 4 合并 | **纯代码** | 聚合 + 校验必填字段/URL/长度 → `PASS` / `NEEDS_RETRY` |
| 5 成稿 | 主模型 | 读合并数据、抽查 2–3 个对象，按场景出报告 |

### 铁律

1. 一个子 Agent 只处理一个对象；
2. 提示词必须窄——只有对象、字段模板、落盘路径；
3. 输出必须短——只写模板字段，超长即打回；
4. 合并走代码——合并环节零 LLM 调用；
5. 每对象一个结果文件——`result/<slug>.json` 就是断点，续跑只补缺。

## 字段模板

按场景给默认值，随时可覆盖：

| 场景 | 默认字段 | 默认产出 |
|---|---|---|
| `financial` | name, ticker, revenue, net_profit, gross_margin, yoy, key_segments, risks, source_urls | CSV/Excel 总表 + 精简报告 |
| `academic` | title, authors, year, venue, research_question, method, findings, limitations, url | 单页可溯源 HTML 综述 |
| `tech` | name, owner, positioning, latest_version, stars, license, activity, pros, cons, url | 对比表 + 分析报告 |

## 合并脚本

```bash
python skill/scripts/merge_results.py --run-dir WideHive/<run_id>
```

stdout 输出 JSON 校验报告：`total_targets` / `ok` / `defects` / `missing_files` / `verdict`（`PASS` 或 `NEEDS_RETRY`，缺陷精确到"哪个对象缺哪个字段"）。纯 Python 标准库，3.8+，无第三方依赖。

## 真实运行存档（见 `examples/smoke-test-3repos/`）

三个 GitHub 仓库、每个一个 worker，跑在原版 AutoClaw / OpenClaw 智能体上：

| 对象 | 版本 | Stars | 协议 | 来源数 |
|---|---|---|---|---|
| LangGraph | v0.4.4 | 41,583 | MIT | 3 |
| CrewAI | v1.15.17 | 58,479* | MIT | 2 |
| AutoGen | v0.12.2 | 58,294 | 代码 MIT / 文档 CC-BY-4.0 | 2 |

\* CrewAI 的 worker 两次检索只找到过期快照数据，按规则诚实写 `null` 而不是编造；合并脚本检出该缺陷后由编排者从 GitHub API 兜底补齐——失败处理闭环按设计工作。

## 环境要求

- 必须：具备子 Agent 派发能力（`sessions_spawn`）且 worker 可读写文件的 AutoClaw / OpenClaw 智能体（或等价环境）；
- 可选：增强网页抓取工具（如 AutoGLM open-link）显著提升抗反爬能力；内置抓取可作为兜底；
- Python 3.8+（合并脚本，仅标准库）。

## FAQ

**和 Deep Research 有什么区别？**
Deep Research 在单一上下文里把一条线挖深；wide research 用隔离上下文把一片面铺宽。两者可组合：先用一个枚举对象，再用另一个扇出。

**100 个对象跑一轮成本多少？**
Worker 用默认模型 + 窄提示词 + 短输出，典型配置下整轮扇出约 1–3M token，成本大头在扇出阶段；合并环节零成本。

**为什么合并用代码不用 LLM？**
因为"把一堆摘要拼成总表"正是幻觉滋生的环节。脚本机械校验字段，只有最终叙事由模型基于已校验数据撰写。

**能在 AutoClaw 之外用吗？**
可以——AutoClaw 本身基于 OpenClaw 运行时构建，WideHive 面向的就是这个运行时：任何 OpenClaw 系发行版都能用 `openclaw skills install widehive` 安装。编排纪律本身与环境无关，可移植。

## 致谢

- 策略思路受 [Manus Wide Research](https://manus.im/blog/introducing-WideHive) 启发；
- 分治-合并模式与验证方法参考 [grapeot/codex_wide_research](https://github.com/grapeot/codex_wide_research)。

## 协议

[MIT](LICENSE)
