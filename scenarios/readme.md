# Scenario packs

A scenario pack is a ready-to-run configuration for one research domain:
field template, worker prompt variant, report layout, and the pitfalls that
domain is known for. Packs are **prompt-only** (no code) so they stay
harness-agnostic.

## Using a pack

Copy the pack's fields into `plan.json`, use its worker prompt variant as the
base template's domain addendum, and follow its report layout in Stage 5.
The pack's pitfalls section doubles as a QA checklist before fan-out.

## Contributing

Add `scenarios/<name>.md` following `financial-filings.md` as the reference
structure:

1. **Targets** — what one object is (a company, a repo, a paper…)
2. **Fields** — the extraction template
3. **Worker prompt variant** — domain addendum to the base worker template
4. **Report layout** — how Stage 5 should synthesize
5. **Pitfalls** — what this domain gets wrong (the most valuable section)

A pack earns its place by surviving at least one real run with archived
results (see `examples/`).
