# Harness adapters

## Purpose

Document how the WideHive five-stage spec maps onto different agent harnesses, so the same orchestration discipline runs anywhere that supports three capabilities: isolated sub-agent spawning, file read/write, and web fetching.

## Contents

- [`openclaw.md`](openclaw.md) — AutoClaw / OpenClaw (canonical, validated environment)
- [`claude-code.md`](claude-code.md) — Claude Code
- [`codex-cli.md`](codex-cli.md) — OpenAI Codex CLI
- [`trae.md`](trae.md) — Trae (字节 AI IDE)
- [`workbuddy.md`](workbuddy.md) — WorkBuddy (腾讯云桌面工作台, CodeBuddy CLI)

Capability matrix:

| Capability | OpenClaw / AutoClaw | Claude Code | Codex CLI | WorkBuddy | Trae |
|---|---|---|---|---|---|
| Isolated sub-agents | `sessions_spawn` | Agent tool (subagents) | shell-run child `codex` | headless CLI workers (`scripts/fanout_cli.py`) | none — serial |
| Parallel fan-out | native waves | native waves | `fanout_cli.py` | `fanout_cli.py` (flags verified) | serial / multi-session |
| Per-worker model tiering | harness override | `--model` per child | `-m` per child | `--model` per worker (`fanout_cli.py`) | per-chat model selector |
| File write/read | `write` / `read` tools | `Write` / `Read` tools | shell + apply_patch | native desktop FS | workspace native |
| Web fetch | `web_search` + open-link / built-in | `WebSearch` / `WebFetch` | browser/search MCP | built-in + MCP | built-in + MCP |
| Scheduling | OpenClaw cron | external cron | external cron | external cron | external cron |
| Zero-LLM merge | `scripts/merge_results.py` | same | same | same (MCP or CLI) | same (MCP or CLI) |

## Usage

Start with `openclaw.md` (the reference mapping). To port: replace the three capability mappings above with your harness's equivalents — every other part of the spec (iron rules, watch mode, corpus, retry playbook, scenario packs) is harness-agnostic and needs no changes.

## Notes

- The spec requires per-worker file write access; agents that only return text break checkpoint/resume (`fanout_cli.py` captures returned JSON from worker stdout as a fallback, marked `patched_by: stdout_capture`).
- Model tiering (`plan.json` → `models.worker` mid-tier, `models.escalate_to` flagship) is spec default policy: workers never run the flagship tier until a mid-tier attempt failed them (`escalate` prescription from the merge verdict).
- Scheduling is external on non-OpenClaw harnesses (cron / Task Scheduler launching the agent CLI).
- Keep adapter docs in sync when the spec changes; the capability matrix is the contract.
