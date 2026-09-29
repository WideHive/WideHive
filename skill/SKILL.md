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

- `plan.json` — scenario, field template, batch_size, max_output_words, max_retries, output_form; model tiers (`models.worker` / `models.escalate_to`, see Stage 3); watch runs add `mode` and a `watch` block (see Watch mode)
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
  (default 2), `output_form`, and `models` —
  `{"worker": "<mid-tier>", "escalate_to": "<flagship>"}`. Workers do narrow,
  template-shaped extraction, so a mid-tier model is the default; the
  flagship tier is reserved for escalated hard objects (see Stage 3).
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
- **Model tiering (default policy).** Workers run on `plan.json`
  `models.worker` (mid-tier); escalated objects run on `models.escalate_to`
  (flagship). Escalate an object when: (a) the merge verdict flags it
  `"escalate": true` (capability-limit defects: invalid JSON, overlong
  output), (b) it has failed `max_retries` rounds at the mid tier, or (c)
  the plan pre-flags it as hard (unstructured / abstract sources). Never
  escalate for missing data or blocked sources — a stronger model cannot
  unblock a fetch; use the fallback ladder instead. On platforms without
  per-worker model override, run the worker sessions on the mid tier
  selected in the platform UI.
- **Headless CLI fan-out.** On harnesses with a CLI agent but no sub-agent
  spawning (WorkBuddy/CodeBuddy, Claude Code, Codex CLI), drive Stage 3 with
  the parallel driver instead of serial in-session processing:

  ```
  python <skill_dir>/scripts/fanout_cli.py --run-dir <run_dir> \
      --concurrency 4 --dry-run     # inspect the plan first
  python <skill_dir>/scripts/fanout_cli.py --run-dir <run_dir> --concurrency 4
  ```

  It spawns one isolated CLI worker per object with concurrency control,
  checkpoint resume, per-worker model override, and a stdout-JSON capture
  fallback for workers that cannot write files. Every outcome is appended to
  `<run_dir>/fanout_log.jsonl` — use it as the timing/cost baseline.
- **Direct-API thin workers (no platform needed).** When the target list
  carries direct URLs (benchmark scans, monitoring lists, batch tables) or no
  agent platform is available at all, drive Stage 3 with the thin worker:

  ```
  python <skill_dir>/scripts/fanout_api.py --run-dir <run_dir> \
      --api-base <openai-compatible-endpoint> --api-key <key> --dry-run
  ```

  The script fetches pages itself (HTML-first ladder; optional Tavily/Bocha
  search for objects without URLs), calls any OpenAI-compatible API for
  extraction only, and builds `sources` from its own fetch records —
  provenance by construction. Same checkpoint/hints/escalate/log contract as
  the CLI driver. Executor tiering composes with model tiering: thin workers
  are the default; objects that come back `fetch_failed` (rendered pages,
  anti-crawl, PDF/video) route to the agent-worker ladder via the retry
  playbook, then escalate the model last.
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
  (`total_targets` / `ok` / `defects` / `missing_files` / `retry_queue` /
  `verdict`). Each defect entry carries a prescription — `retry_hint`
  (one-line fix instruction), `escalate` (capability-limit defect → retry on
  `models.escalate_to`), `patchable` (only missing fields → patch directly).
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

## Watch mode (scheduled monitoring)

A one-shot run answers a question once. Watch mode turns a target list into a
**continuously monitored feed**: on a schedule, diff against the previous run,
re-fan-out only what changed, and emit a change report.

Enable it in `plan.json`:

```json
{
  "mode": "watch",
  "watch": {
    "baseline_run": "widehive/<previous_run_id>",
    "compare_fields": ["revenue", "gross_margin", "latest_version"],
    "schedule": "0 9 * * 1"
  }
}
```

`schedule` is informational — the platform cron job owns timing; keep it
human-readable. The scheduled run flow, triggered by a cron job whose prompt is
"Run WideHive watch run <run_id>":

1. Diff first, zero LLM and zero fan-out cost:
   `python <skill_dir>/scripts/diff_results.py --baseline <prev_run_dir> --current <cur_run_dir>`
2. **No new/changed objects** → carry results forward, emit a one-paragraph
   no-change note. Total cost ≈ 0.
3. **New/changed objects exist** → fan out workers only for those slugs
   (narrow prompts as usual), copy unchanged `result/*.json` forward from the
   baseline run so the merge covers the full list, then merge and produce a
   **change report**: what changed, per field, with sources.
4. Promote the current run to baseline (update the watch pointer / run list).

**Politeness**: schedule no faster than the target sources actually update;
add jitter; respect robots and ToS. A watch that hammers its sources gets
blocked — and burns trust for the skill, the user, and the wider ecosystem.

## Multimodal objects

An object is not always a web page. The fetch ladder extends to:

- **PDF / documents** — native PDF tooling at the worker; extract per template.
- **Video** — fetch the transcript first (platform ASR / transcript tools);
  sample visual frames only when the template actually needs them. Record the
  transcript source and timestamp coverage in the result.
- **Audio** — same as video, minus frames.
- **Images** — vision-capable analysis at the worker; store the image URL plus
  the observed facts, never the image itself.

Worker prompts stay narrow: tell the worker which modality the object is and
which tool tier to try first, exactly as with fetching. If a modality cannot
be processed on the current platform, write the object with
`"error":"unsupported_modality"` instead of silently dropping it.

## Corpus (knowledge base across runs)

Every finished run is knowledge. Before answering any question about
already-researched objects, query the corpus — do not re-fan-out and do not
re-search.

Build / refresh (after every Stage 5 and every watch run):

```python
python <skill_dir>/scripts/build_corpus.py --runs-root <workspace>/widehive --out <workspace>/widehive-corpus
```

Query rules for the main session:

1. Answer strictly from `corpus.jsonl` / `corpus-index.json`; cite the run_id
   and `fetched_at` of every figure.
2. Stale beats invented: if the corpus answer is older than the user's
   freshness need, say so and offer a targeted re-run of just the affected
   objects (watch mode's diff does this automatically).
3. If the corpus lacks the requested data, say what's missing and propose the
   narrowest fan-out that would fill the gap.

## Dashboard (interactive output)

Optional Stage 5 add-on: turn `merged.json` into a self-contained interactive
dashboard — search, sort, per-object drill-down with sources, numeric bar
charts — no external dependencies, double-click to open:

```python
python <skill_dir>/scripts/build_dashboard.py --merged <run_dir>/merged.json --out <run_dir>/dashboard.html
```

## Tabular intake & write-back

For non-technical initiators, targets and results can move through tables:

- **Intake**: accept a target list as CSV/TSV (slug, name, url, …) or a
  spreadsheet / bitable table; convert to `targets.json` at Stage 1 and show
  the parsed list for confirmation as usual.
- **Write-back**: after Stage 4, append `merged.csv` rows back to the intake
  table as new columns prefixed `wh_` (or a companion sheet/table); never
  overwrite user-owned columns.
- **Schedules**: a cron prompt may point at a table whose rows changed since
  the last run — combine with watch mode's diff to monitor a living list.

## Default field templates (override freely)

- `financial`: name, ticker, revenue, net_profit, gross_margin, yoy, key_segments, risks, source_urls
- `academic`: title, authors, year, venue, research_question, method, findings, limitations, url
- `tech`: name, owner, positioning, latest_version, stars, license, activity, pros, cons, url

## Cost & concurrency discipline

- Start at `batch_size=10`; for 100+ objects ramp 5→10→15 first to probe how
  many concurrent sub-agents the platform tolerates, then go full width.
- **Model tiering is the default, not an option.** Enumeration and synthesis
  need the strong model; workers produce narrow, template-shaped output and
  run `models.worker` (mid-tier). Only escalated objects spend flagship
  budget, and only after a mid-tier attempt failed them. Never spend
  strong-model budget inside a worker that has not failed at least once.
- Cost is controlled by model tiering + narrow prompts + short outputs, not
  by a bigger budget.
- The run directory is the single source of truth; any interruption resumes
  from `result/`.

## Failure handling & retry playbook

The merge verdict prescribes the fix per object via `retry_queue`
(`patch_first` / `retry` / `escalate`). Work the ladder in order per object;
stop at the first success and record which rung was used:

1. **Patch first (`patch_first`)** — only deterministic fields are missing (a
   number, a URL, a date): the orchestrator fetches and patches
   `result/<slug>.json` directly, disclosing "patched by fallback" in the
   final report. One targeted fetch beats one worker round-trip.
2. **Targeted re-dispatch (`retry`)** — re-run the worker with the
   `retry_hint` injected: fix ONLY this defect, keep the rest of the existing
   file. Transient infrastructure errors (LLM request failure, gateway
   timeout) clear here. Max `max_retries` rounds.
3. **Escalated re-dispatch (`escalate`)** — same targeted prompt on
   `models.escalate_to`. Capability limits (invalid JSON, overlong output)
   are what a stronger model actually fixes; escalate nothing else.
4. **Alternate source type / fetch engine** — official PDF → authoritative
   media → secondary source, disclosing the downgrade; dedicated web-open
   tool → built-in fetch. Take this rung BEFORE escalating when the hint is
   source-blocked (`worker_error`): a bigger model cannot unblock a fetch.
   If infrastructure failures arrive in batches, pause fan-out and check the
   platform before continuing.
5. **Disclose** — objects that exhaust the ladder are marked skipped in the
   final report. Never silently drop an object; a blocked fetch is written as
   `{"fields":{...},"error":"fetch_failed"}` so the merge script accounts
   for it.

Track retry rounds in the run dir (`retry-queue.json`; optional but
recommended for large fan-outs). Stage 4 is done only when every object
converged or every skip is disclosed.

With `fanout_cli.py`, feed the verdict back as the retry input — the driver
injects each `retry_hint` into the worker prompt and routes escalated slugs
to the escalate_to model automatically:

```
python <skill_dir>/scripts/merge_results.py --run-dir <run_dir> > <run_dir>/verdict.json
python <skill_dir>/scripts/fanout_cli.py --run-dir <run_dir> \
    --hints <run_dir>/verdict.json --slugs <retry_queue slugs> --force
```

## Prerequisites

- Required: a sub-agent spawning capability (AutoClaw / OpenClaw `sessions_spawn` or
  equivalent) with file read/write tools for workers.
- Optional: enhanced web-open tools (e.g. AutoGLM open-link) meaningfully
  improve anti-crawl fetching; the platform's built-in fetch works as fallback.
- Porting to another harness: see [`../adapters/README.md`](../adapters/README.md)
  for per-harness mappings (OpenClaw, Claude Code, codex CLI).
