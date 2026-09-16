# Changelog

All notable changes to this project are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.3.0] - 2026-09-16

### Added

- **Corpus (knowledge base across runs)**: `scripts/build_corpus.py` consolidates
  finished runs into `corpus.jsonl` + an index; query discipline added to the
  spec (answer from the corpus first, cite run + fetch date, targeted re-runs
  for gaps — never re-fan-out to answer an already-researched question).
- **Interactive dashboard**: `scripts/build_dashboard.py` turns merged.json into
  a self-contained HTML dashboard (search / sort / drill-down with sources /
  numeric bar charts), no external dependencies.

## [1.1.0] - 2026-09-16

### Added

- **Watch mode (scheduled monitoring)**: set `mode: "watch"` plus a `watch`
  block in `plan.json`; new `scripts/diff_results.py` diffs a current run
  against a baseline (zero LLM), and the orchestrator re-fans-out **only**
  new/changed objects, carrying unchanged results forward. Idle scheduled runs
  cost ≈ 0.
- **Scenario packs** (`scenarios/`): prompt-only domain configurations. First
  pack: `financial-filings` — prospectus/annual-report extraction with currency
  discipline, IFRS-vs-adjusted separation, and a validated report layout
  (survived a real 4-object run).
- **Model tiering guidance**: strong model for enumerate/synthesize; default or
  cheaper model for workers.
- **Retry playbook**: ordered fallback ladder (retry → alternate source →
  alternate fetch engine → field-level fallback → disclose skipped).

## [1.0.0] - 2026-09-16

### Added

- Five-stage orchestration spec: Plan → Enumerate → Fan out → Merge → Synthesize.
- `scripts/merge_results.py`: zero-LLM programmatic merge with field / URL /
  length validation and a JSON verdict report (`PASS` / `NEEDS_RETRY`).
- Checkpoint-resume semantics: one `result/<slug>.json` per object; interrupted
  runs resume by only redoing missing objects.
- Default field templates for three scenarios: `financial`, `academic`, `tech`
  (all overridable via `plan.json` or per-run instructions).
- Backend fallback chain for web fetching: dedicated web-open tools (e.g.
  AutoGLM open-link) → platform built-in fetch → explicit `fetch_failed` marker
  (objects are never silently dropped).
- Retry queue with bounded rounds plus an orchestrator fallback rule for
  infrastructure-type worker failures.
- Worked example: `examples/smoke-test-3repos/` — an archived real run over
  three GitHub repositories with `verdict: PASS`.
