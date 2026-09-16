# Harness adapters

## Purpose

Document how the WideHive five-stage spec maps onto different agent harnesses, so the same orchestration discipline runs anywhere that supports three capabilities: isolated sub-agent spawning, file read/write, and web fetching.

## Contents

- [`openclaw.md`](openclaw.md) — AutoClaw / OpenClaw (canonical, validated environment)
- [`claude-code.md`](claude-code.md) — Claude Code
- [`codex-cli.md`](codex-cli.md) — OpenAI Codex CLI

Capability matrix:

| Capability | OpenClaw / AutoClaw | Claude Code | Codex CLI |
|---|---|---|---|
| Isolated sub-agents | `sessions_spawn` | Agent tool (subagents) | shell-run child `codex` |
| File write/read | `write` / `read` tools | `Write` / `Read` tools | shell + apply_patch |
| Web fetch | `web_search` + open-link / built-in | `WebSearch` / `WebFetch` | browser/search MCP |
| Scheduling | OpenClaw cron | external cron | external cron |
| Zero-LLM merge | `scripts/merge_results.py` | same | same |

## Usage

Start with `openclaw.md` (the reference mapping). To port: replace the three capability mappings above with your harness's equivalents — every other part of the spec (iron rules, watch mode, corpus, retry playbook, scenario packs) is harness-agnostic and needs no changes.

## Notes

- The spec requires per-worker file write access; agents that only return text break checkpoint/resume (the orchestrator can write returned JSON as a fallback, at the cost of atomicity).
- Scheduling is external on non-OpenClaw harnesses (cron / Task Scheduler launching the agent CLI).
- Keep adapter docs in sync when the spec changes; the capability matrix is the contract.
