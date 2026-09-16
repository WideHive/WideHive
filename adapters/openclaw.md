# Adapter: OpenClaw / AutoClaw (canonical)

This is the environment WideHive was designed and validated in.

| Spec concept | OpenClaw mapping |
|---|---|
| Stage 3 worker | `sessions_spawn` — isolated one-shot sub-agent, `label` = `WideHive·<scenario>·<NN>`, narrow prompt in the user's language |
| Waiting | Push-based: end the turn (`sessions_yield`) and handle completion events between waves |
| Result write | Worker uses the `write` tool to produce `result/<slug>.json` |
| Fetch ladder | dedicated web-open tools (e.g. AutoGLM open-link) → built-in web fetch → `fetch_failed` |
| PDF objects | worker-native PDF tool |
| Merge (Stage 4) | `python <skill_dir>/scripts/merge_results.py --run-dir <run_dir>` |
| Diff (watch) | `python <skill_dir>/scripts/diff_results.py --baseline <prev> --current <cur>` |
| Corpus | `python <skill_dir>/scripts/build_corpus.py --runs-root <workspace>/widehive` |
| Dashboard | `python <skill_dir>/scripts/build_dashboard.py --merged <run_dir>/merged.json` |
| Scheduling | OpenClaw cron job; prompt = "Run WideHive watch run <run_id>" |
| Tabular intake | Feishu/CSV table → `targets.json`; write-back appends `wh_*` columns |

## Notes

- Do not pass a model override to workers unless you have a deliberate
  tiering plan (see spec: Model tiering).
- Batched dispatch: waves of `batch_size`; end the turn after each wave.
- The orchestrator (main session) never fetches per-object data itself —
  workers do; the orchestrator only reads `merged.json` in Stage 5.
