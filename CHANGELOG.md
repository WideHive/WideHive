# Changelog

All notable changes to this project are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
