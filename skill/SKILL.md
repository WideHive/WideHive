---
name: widehive
description: "WideHive — Wide Research orchestration for AutoClaw / OpenClaw agents: fan out 100+ context-isolated sub-agents over a large target list, merge programmatically with zero LLM calls, synthesize scenario-shaped reports (financial tables / academic reviews / tech matrices). Triggers: widehive, wide research, batch research, 批量调研, 大范围调研."
---

# WideHive

> A hive of agents for wide questions. — 把一个问题，交给一整个蜂巢。

Large task → split into N independent subtasks → each subtask handled by one
context-isolated sub-agent in parallel → merge with code (not LLM) → synthesize
the final report with the main model.

Use this when a research task has **≥ 20 target objects** (papers, companies,
repos, products…). With fewer than ~10 objects, just do the task directly in the
main session — the orchestration overhead is not worth it.

## Why this works (read once)

LLMs start "slacking off" once their output fills 20–50% of the context window:
they skip sentences, compress, paraphrase. WideHive sidesteps this with
divide-and-conquer: each sub-agent gets a tiny isolated context, so every output
stays short and faithful; the merge step is pure code, so aggregation adds zero
hallucination.

Credit: the strategy follows Manus Wide Research, and the divide-merge pattern
is validated by the open-source `codex_wide_research` experiment (53/53 blog
posts summarized with zero hallucinations, where single-context baselines
covered only 12–20 before stalling).

## Iron rules (violating any of these reverts you to the slacking/hallucinating baseline)

1. **One object per sub-agent.** Never batch multiple objects into one worker.
2. **Narrow worker prompts.** Give the worker only: the object, the field
   template, the output path. No task background, no history.
3. **Short worker outputs.** Template fields only; overlong output = failure,
   send back to the retry queue.
4. **Merge with code.** Run `scripts/merge_results.py`; zero LLM calls in the
   merge stage.
5. **One file per object.** `result/<slug>.json` is the checkpoint — resume
   only what is missing, never redo finished objects.

## Run directory

`widehive/<run_id>/` under the workspace (scratch/test runs may live in a
tmp directory instead):

- `plan.json` — scenario, field template, batch_size, max_output_words, max_retries, output_form
- `targets.json` — object list (`slug`, `name`, `url`/identifier, source hint)
- `result/<slug>.json` — one file per object, written by the worker
- `merged.csv` / `merged.json` — programmatic merge output
- `report.*` — final deliverables

## Stage 1 — Plan (main session)

- Input already contains an explicit target list → skip Stage 2.
- Input is just a topic → Stage 2 is required.
- Decide scenario: `financial` / `academic` / `tech` / `custom` (infer from the
  task; ask one question if unsure).
- Write `plan.json`: scenario, `fields` (default per scenario, see below),
  `batch_size` (default 10), `max_output_words` (default 400), `max_retries`
  (default 2), `output_form`.
- Show the user a short task brief (object count, what gets extracted per
  object, rough cost scale) before fanning out. Converge before you spend.

## Stage 2 — Enumerate (topic mode only, main session)

- Run web searches to build the candidate object list (name + URL/identifier +
  one-line source hint), write `targets.json`.
- Show the full list to the user for confirmation. Only fan out after the user
  locks the list.

## Stage 3 — Fan out (batched sub-agents)

- List existing `result/` files → skip finished objects (checkpoint resume).
- Dispatch workers in waves of `batch_size`, using your platform's sub-agent
  spawning (AutoClaw / OpenClaw: `sessions_spawn`, isolated one-shot). Label:
  `WideHive·<scenario>·<NN>`. Waiting is push-based — end the turn and
  handle completion events; report progress briefly between waves.
- Failed objects (no result file / missing fields / overlong / session failure)
  go to the retry queue, at most `max_retries` rounds; still-failing objects
  are disclosed as skipped in the final report.

**Worker prompt template** (dispatch in the user's language):

```
You are a Wide Research single-object worker. Handle ONLY this one object;
do not expand scope.

Object: <name> (<url or unique identifier>)
Task:
1. Fetch first-hand info about this object. Prefer official / authoritative
   sources. Use the best web tool available on this platform (dedicated
   web-open tools first, built-in web fetch as fallback). At most 3
   searches/fetches.
2. Extract strictly per the field template. If a value cannot be verified,
   write null — never guess:
   <field list>
3. Write the result with the file-write tool to:
   <absolute path>/result/<slug>.json (UTF-8), structure:
   {"target":"<name>","fields":{...},"sources":[{"title":"...","url":"..."}],
    "fetched_at":"<today's date>"}
4. If no file-write tool is available, return the same JSON verbatim as your
   final output.

No long prose. Write the file and finish.
```

## Stage 4 — Merge (zero LLM)

```
python <skill_dir>/scripts/merge_results.py --run-dir <run_dir>
```

- Aggregates `result/*.json` → `merged.csv` + `merged.json`; validates required
  fields, URL format, and field length; prints a JSON verdict report
  (`total_targets` / `ok` / `defects` / `missing_files` / `verdict`).
- `verdict: NEEDS_RETRY` → queue defective objects back to Stage 3.
- The script's report is the single source of truth for fan-out quality —
  never eyeball-approve a result that the script flagged.

## Stage 5 — Synthesize (main session)

- Read `merged.json` (do not re-read raw pages), spot-check 2–3 objects against
  their sources.
- Deliver per scenario (user can override):
  - `financial`: CSV/Excel metric table first + compact comparison report
  - `academic`: single-page clickable HTML review (taxonomy + per-object
    traceable summaries with source links)
  - `tech`: comparison table + analysis report (decision matrix + reasoning)
  - `custom`: agree on the shape with the user
- Ship the raw `result/` directory alongside the report — per-object results
  are never truncated, always verifiable.

## Default field templates (override freely)

- `financial`: name, ticker, revenue, net_profit, gross_margin, yoy, key_segments, risks, source_urls
- `academic`: title, authors, year, venue, research_question, method, findings, limitations, url
- `tech`: name, owner, positioning, latest_version, stars, license, activity, pros, cons, url

## Cost & concurrency discipline

- Start at `batch_size=10`; for 100+ objects ramp 5→10→15 first to probe how
  many concurrent sub-agents the platform tolerates, then go full width.
- Workers run on the default model. Cost is controlled by narrow prompts +
  short outputs, not by a bigger budget.
- The run directory is the single source of truth; any interruption resumes
  from `result/`.

## Failure handling

- Worker session failed / timed out → object stays in the retry queue
  (max `max_retries` rounds), then disclose as skipped.
- Fetch blocked / anti-crawl → retry once via an alternative fetch path; if
  still failing, write `{"fields":{...},"error":"fetch_failed"}` so the merge
  script accounts for it. Never silently drop an object.
- Orchestrator fallback: if a retry worker also fails with an
  infrastructure-type error (LLM request failure, gateway timeout) and only a
  few deterministically fetchable fields are missing, the orchestrator may
  fetch and patch the file directly, disclosing "patched by fallback" in the
  report. If infrastructure failures arrive in batches, pause fan-out and
  check the platform before continuing.
- Stage 4 is done only when every object converged or every skip is disclosed.

## Prerequisites

- Required: a sub-agent spawning capability (AutoClaw / OpenClaw `sessions_spawn` or
  equivalent) with file read/write tools for workers.
- Optional: enhanced web-open tools (e.g. AutoGLM open-link) meaningfully
  improve anti-crawl fetching; the platform's built-in fetch works as fallback.
