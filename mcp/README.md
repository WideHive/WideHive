# WideHive MCP server

Exposes the WideHive pipeline as an **MCP server**: four zero-LLM tools
(merge / diff / corpus / dashboard) plus the orchestration spec as a resource
and prompt. Any MCP-compatible agent platform (OpenClaw, Trae, Claude Code,
Cursor, Dify via MCP bridge, …) can call these tools — the host agent plays
the orchestrator, WideHive provides the deterministic machinery.

## Tools

| Tool | Input | Output |
|---|---|---|
| `merge_results` | run_dir, required_fields? | PASS/NEEDS_RETRY verdict JSON (per-object defects) |
| `diff_results` | baseline, current, compare_fields? | watch diff summary + per-field changes |
| `build_corpus` | runs_root, out? | corpus.jsonl + index stats |
| `build_dashboard` | merged, out?, title? | self-contained interactive dashboard HTML |

Resources: `widehive://spec/SKILL.md`, `widehive://spec/scenarios/financial-filings.md`.
Prompt: `widehive_orchestration` — the full spec text for agents without resource support.

## Setup

```bash
git clone https://github.com/WideHive/WideHive.git
pip install "mcp[cli]"
```

### Client configuration (generic JSON, works in Trae / Claude Code / Cursor / Cline)

```json
{
  "mcpServers": {
    "widehive": {
      "command": "python",
      "args": ["<repo>/mcp/server.py"]
    }
  }
}
```

Scripts resolve relative to `server.py` (`../skill/scripts/`). Override with
the `WIDEHIVE_SCRIPTS_DIR` environment variable if you use a custom layout.

### HTTP/SSE transport (for platforms that call remote MCP endpoints)

```bash
python server.py --transport sse --port 8808
```

## Requirements

- Python 3.10+ with the `mcp` package (`pip install "mcp[cli]"`)
- The host agent must be able to spawn sub-agents and read/write files to run
  the full five-stage flow — see `../adapters/` for per-harness notes.
