# Archived smoke run — 3 GitHub repositories (2026-09-14)

A real end-to-end run of the WideHive pipeline on a stock AutoClaw /
OpenClaw agent, archived as a worked example.

**Setup**: scenario `tech`, 3 targets, one isolated sub-agent worker per repo,
batch_size 3. Workers fetched first-hand data (GitHub API / official docs),
extracted the field template, and wrote one JSON file per object.

**What happened**

1. All 3 workers wrote their result files (`result/*.json`).
2. First merge flagged one defect: CrewAI's worker could not verify a current
   star count (search snapshots were stale) and wrote `null` instead of
   guessing — `verdict: NEEDS_RETRY`.
3. The orchestrator fetched the value from the GitHub API directly
   (infrastructure fallback for a failed retry worker) and patched the file.
4. Re-merge: `verdict: PASS`, zero hallucinated values.

**Files**

- `plan.json` / `targets.json` — the run configuration
- `result/langgraph.json`, `result/crewai.json`, `result/autogen.json` — raw worker outputs
- `merged.csv` / `merged.json` — programmatic merge output

Star counts are point-in-time snapshots from the run date, not live values.
