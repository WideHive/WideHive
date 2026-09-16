# Scenario packs

## Purpose

Scenario packs are prompt-only domain configurations that make WideHive immediately useful in a specific research domain — no code, no new dependencies. Each pack defines what an object is, what to extract, how workers should be prompted, and what the final report looks like.

## Contents

- [`financial-filings.md`](financial-filings.md) — prospectus / annual-report extraction and company comparison (validated by a real 2-company × 4-document run, archived under `examples/`)

## Usage

- Copy the pack's field template into `plan.json`.
- Apply the pack's worker prompt variant on top of the base template in [`../skill/SKILL.md`](../skill/SKILL.md).
- Follow the report layout in Stage 5; the pack's pitfalls section doubles as a pre-fan-out QA checklist.

## Notes

- Contributing: add `scenarios/<name>.md` following `financial-filings.md` as the reference structure (Targets / Fields / Worker prompt variant / Report layout / Pitfalls).
- A pack earns its place by surviving at least one real run with archived results under `examples/`.
- Packs are English-only; dispatch language follows the user.
