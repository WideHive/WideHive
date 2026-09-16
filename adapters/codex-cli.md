# Adapter: Codex CLI

Maps the WideHive five stages onto OpenAI Codex CLI child processes
(same spirit as grapeot/codex_wide_research, formalized).

| Spec concept | Codex CLI mapping |
|---|---|
| Stage 3 worker | Main Codex spawns child `codex` processes via shell (one per object), args carry the narrow prompt |
| Result write | Child writes `result/<slug>.json` via shell (`apply_patch` or redirect) |
| Fetch ladder | Browser/search MCP (playwright / chrome-devtools / tavily) → built-in browsing → `fetch_failed` |
| Merge / Diff / Corpus / Dashboard | Same Python scripts, run via shell |
| Scheduling | External cron launching `codex` with the watch prompt |
| Approval | Prefer a sandbox/approval mode that lets children write files without per-file prompts |

## Notes

- This adapter predates the others conceptually: the original
  codex_wide_research proved the pattern; WideHive formalizes it (watch mode,
  corpus, retry ladder, scenario packs).
- Shell-level fan-out means the orchestrator script handles batching and
  failure collection — keep `batch_size` modest and collect exit codes.
