# Harness adapters

WideHive is spec-first: the five stages + iron rules map onto any agent harness
that can do three things —

1. **Spawn isolated sub-agents** (one object per worker, narrow prompt);
2. **Read/write files** (per-object result files are the checkpoint);
3. **Fetch web content** (search + page/PDF retrieval, with a fallback chain).

This folder documents the mapping per harness. Start with the canonical one:

- [`openclaw.md`](openclaw.md) — AutoClaw / OpenClaw (canonical, best supported)
- [`claude-code.md`](claude-code.md) — Claude Code
- [`codex-cli.md`](codex-cli.md) — OpenAI Codex CLI

## Capability matrix

| Capability | OpenClaw / AutoClaw | Claude Code | Codex CLI |
|---|---|---|---|
| Isolated sub-agents | `sessions_spawn` | Agent tool (subagents) | shell-run child `codex` |
| File write/read | `write` / `read` tools | `Write` / `Read` tools | shell + apply_patch |
| Web fetch | `web_search` + open-link / built-in | `WebSearch` / `WebFetch` | browser/search MCP |
| Scheduling | OpenClaw cron | external cron | external cron |
| Zero-LLM merge | `scripts/merge_results.py` | same | same |

Everything else in the spec (iron rules, watch mode, corpus, retry playbook)
is harness-agnostic and works unchanged once the three capabilities map.
