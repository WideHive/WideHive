# Adapter: Claude Code

Maps the WideHive five stages onto Claude Code's Agent tool.

| Spec concept | Claude Code mapping |
|---|---|
| Stage 3 worker | Agent tool (subagent), one object per agent; run in background and collect results |
| Result write | Worker uses the `Write` tool to produce `result/<slug>.json` |
| Fetch ladder | `WebFetch` (dedicated) → `WebSearch` → note `fetch_failed` |
| PDF objects | PDF reading support in the agent context |
| Merge / Diff / Corpus / Dashboard | Same Python scripts, run via shell |
| Scheduling | No native cron — use OS scheduler (cron / Task Scheduler) to launch `claude -p "Run WideHive watch run <run_id>"` |

## Notes

- Keep one object per agent; batch waves to respect platform concurrency.
- Workers must write files (not just return text) so checkpoint/resume works;
  if an agent returns JSON instead, the orchestrator writes the file before
  merging.
- The retry playbook applies unchanged (retry → alternate source → alternate
  engine → field-level fallback → disclose).
