# Archived smoke run — 3 GitHub repositories (2026-09-14)

## Purpose

A real end-to-end WideHive run, archived as a worked example: 3 GitHub repositories, one context-isolated worker each, proving fan-out → merge → validation with zero hallucinated values.

## Contents

- `plan.json` / `targets.json` — run configuration (scenario `tech`, 3 targets)
- `result/langgraph.json`, `result/crewai.json`, `result/autogen.json` — raw per-object worker outputs with sources
- `merged.csv` / `merged.json` — programmatic merge output (verdict: PASS)

## Usage

- Read `merged.csv` for the outcome table (version / stars / license / positioning).
- Open any `result/*.json` to inspect the raw extraction and cited sources.
- Reuse as a template: the matching dispatch prompts live in [`../prompts/example-tasks.md`](../prompts/example-tasks.md).

## Notes

- Star counts are point-in-time snapshots (2026-09-14), not live values.
- The CrewAI entry is intentionally `null`-then-patched: the worker couldn't verify a current star count, the merge flagged it, and the orchestrator filled it from the GitHub API — the failure loop working as designed.
- Dispatch prompts were English; Chinese dispatch works identically (see the spec's worker prompt template).
