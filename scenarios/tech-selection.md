# Scenario pack: tech-selection

Compare any set of GitHub repos / open-source libraries / dev tools and
produce a decision-ready selection matrix. Validation status: smoke-level
(3-repo end-to-end run, verdict PASS, archived at
`examples/smoke-test-3repos/` — including one full null → merge-flag →
patched-by-fallback loop). A 50+ object real run is the next validation
milestone.

## Targets

One object = **one repo / one package / one tool**. List fields:

- `slug` — stable identifier (suggest `<owner>--<repo>`, e.g.
  `langchain-ai--langgraph`; double dash avoids collisions with dots in
  package names)
- `name` / `owner`
- `url` — canonical repo URL (the redirect target, not an alias)
- registry hint (optional): `npm` / `pypi` / `maven` / `none` — required for
  monorepo sub-packages, otherwise workers may grab the wrong version

## Fields

Core fields (go into `plan.json` `fields`; merge-enforced):

```
name, owner, repo_url, language, latest_version, latest_release_date,
license_spdx, stars, last_commit_date, maintenance_status, positioning
```

`maintenance_status` enum (workers fill by definition, no fuzzy words):

| Value | Definition |
|---|---|
| `active` | last commit ≤ 3 months |
| `slow` | last commit 3–12 months |
| `stale` | > 12 months since last commit, not archived |
| `archived` | GitHub shows the Archived banner |

Deep-tier fields (optional; listing them in `fields` adds CSV columns — run
the merge with `--required-fields` naming only the core set so nullable
fields don't trigger NEEDS_RETRY):

```
docs_url, docs_quality, open_issues, cve_notes, integration_notes
```

## Worker prompt variant（叠加在基础模板之上）

- **Source ladder**: repo main page HTML (carries stars, license badge, last
  commit, archived banner; no rate limit) → `api.github.com/repos/<owner>/<repo>`
  JSON (only when the HTML page is insufficient; unauthenticated quota is
  60 req/hour per source IP, shared across ALL parallel workers) →
  Releases page or package registry (version + release date) → official docs
  homepage (the one-line positioning).
- **Identity check**: confirm the canonical repo first (redirects, "moved to"
  banners, org migrations); `repo_url` gets the final landing URL. Same-name
  packages on different registries can be different projects — identify by
  repo_url, never by name string.
- **Version rules**: record as published (`v3.2.1` or `3.2.1`, keep source
  form); append `(pre)` for pre-releases; monorepo sub-packages take the
  registry version plus a `monorepo:<org/repo>` note; add provenance and date
  in parentheses (convention from the smoke run:
  `0.4.4 (GitHub latest Release, 2026-08-27)` — write it in the dispatch
  language).
- **License**: SPDX id (`MIT` / `Apache-2.0`); for dual licenses record both
  joined by ` / ` (e.g. `MIT / Apache-2.0`); when the GitHub badge and the
  LICENSE file disagree, the LICENSE file wins; non-standard licenses fill
  `Other` and explain the grant terms in a deep-tier field.
- **Health**: `maintenance_status` per the enum table; `stars` is a
  point-in-time snapshot and must never be used as a health proxy.
- **pros / cons**: ≤ 25 words each; every entry must cite a concrete fact
  (version, license, docs, architecture decision) — no vibes.
- Unverifiable → `null`. Security fields record only what official advisory
  pages (GitHub Advisories / the project security page) actually list — never
  infer "no vulnerabilities".

## Report layout (Stage 5)

1. **Decision matrix** — `merged.csv` as the base table; columns grouped by
   identity / health / risk / fit, sorted by `maintenance_status` best-first.
2. **Shortlist** — 2–3 candidates, one verdict paragraph each; every verdict
   must trace back to specific cells in the matrix.
3. **License risk table** — one row per non-permissive license with concrete
   commercial-use implications (AGPL-3.0 / SSPL / BSL-type licenses must be
   surfaced explicitly, never silently merged in).
4. **Recommendation + avoid-if** — pick a winner AND write under what
   conditions each candidate is the wrong choice (e.g. closed-source
   commercial integration → avoid AGPL).
5. **Gaps & disclosure** — null fields, skipped objects, source tiers,
   shipped alongside the report.
6. Optional: `build_dashboard.py` for a searchable, sortable interactive
   matrix.

## Watch config example

Selection is not one-shot — turn the list into a continuously monitored
dependency/competitor feed:

```json
{
  "mode": "watch",
  "watch": {
    "baseline_run": "widehive/techsel-<date>",
    "compare_fields": ["latest_version", "last_commit_date",
                        "maintenance_status", "open_issues"],
    "schedule": "0 9 * * 1"
  }
}
```

## Pitfalls (from real runs and domain experience)

- **Stars ≠ maintained**: 40k-star archived repos exist. Health is only ever
  `last_commit_date` + `maintenance_status`; stars are a community-size
  reference at best.
- **The GitHub API's 60 req/hour quota is per source IP, shared across all
  parallel workers**: 100 workers hitting the API fan out into a mid-run 403
  storm that looks like mass worker failure. Prefer the HTML-first ladder;
  raise to 5,000 req/hour when a `GITHUB_TOKEN` env var is available; never
  retry-loop a 403 — treat it as `fetch_failed` and walk the fallback ladder.
- **Dual licensing is the norm, not the exception** (especially Rust's
  `MIT / Apache-2.0`): filling only one manufactures a license risk that
  isn't there; evaluate shortlist entries on their most permissive acceptable
  license.
- **License-change history**: MongoDB / Redis / Elastic all have precedents.
  For commercial-sensitive selections, note documented license changes in the
  shortlist verdict — only when the source page explicitly records them.
- **Fork / canonical confusion**: in elasticsearch→opensearch-style forks the
  original name still exists — a name match is not an object match; identify
  by canonical repo_url only.
- **Monorepo sub-package version ≠ repo Release**: npm/PyPI package versions
  come from the registry; the GitHub Release date is a reference at best.
  Record both.
- **Mirrors and tutorial sites lag** (gitee mirrors, localized reposts): all
  numeric fields come from the canonical upstream; if only a mirror is
  reachable, record the mirror URL and disclose it in the report.
- **`null` discipline**: an empty `cve_notes` is not "no vulnerabilities";
  vulnerability facts require an official advisory page, otherwise `null` and
  disclose in the gaps section — this is the credibility floor of a
  selection report.
