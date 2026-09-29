#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WideHive Stage 4 - programmatic merge & validation (zero LLM).

Usage:
  python merge_results.py --run-dir <run_dir> [--required-fields f1,f2] [--max-field-len 4000]

Inputs:
  <run_dir>/plan.json     {"scenario": ..., "fields": [...], ...}
  <run_dir>/targets.json  [{"slug": ..., "name": ..., "url": ...}, ...]
  <run_dir>/result/*.json one file per object (written by workers)

Outputs:
  <run_dir>/merged.json   merged full records
  <run_dir>/merged.csv    flattened table (UTF-8-SIG, opens directly in Excel)
  stdout: JSON verdict report
          {total_targets, with_results, ok, missing_files, defects, retry_queue, verdict}

verdict: PASS        = every object has a result and no defects
        NEEDS_RETRY  = missing/defective objects, send them back to the retry queue

Retry prescription (added to every defect entry, drives Stage 3 re-dispatch):

  retry_hint   one-line instruction for the retry prompt: fix only this defect
  escalate     true = defect suggests a capability/instruction-following limit
               (json_parse_error, field_too_long) -> retry on the escalate_to
               model tier. Source-blocked or missing-data defects do NOT
               escalate: a bigger model cannot unblock a fetch, use the
               fallback ladder instead.
  patchable    true = the only issues are missing_field -> the orchestrator
               can fetch the missing values directly and patch the result
               file (fallback ladder rung 4) instead of re-running a worker.

  retry_queue  convenience grouping of slugs by prescription:
               {"patch_first": [...], "retry": [...], "escalate": [...]}
               Objects with no result file are dispatched under "retry"
               (first failure is usually infra, not capability).
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

URL_RE = re.compile(r"^https?://\S+$", re.I)


def prescribe(slug, issues, missing_file, max_len):
    """Return (retry_hint, escalate, patchable) for one object's defect list."""
    if missing_file:
        return ("no result file - dispatch failure or worker crashed; "
                "re-dispatch the worker unchanged"), False, False

    kinds = set()
    for i in issues:
        if i.startswith("json_parse_error"):
            kinds.add("parse")
        elif i.startswith("worker_error"):
            kinds.add("worker")
        elif i.startswith("field_too_long"):
            kinds.add("long")
        elif i.startswith("bad_source_url"):
            kinds.add("url")
        elif i.startswith("missing_field"):
            kinds.add("missing")

    miss = sorted(i.split(": ", 1)[1] for i in issues
                  if i.startswith("missing_field: "))
    longs = sorted(i.split(" ", 1)[1] for i in issues
                   if i.startswith("field_too_long: "))

    if kinds == {"missing"}:
        return (f"fetch and verify only the missing field(s) {miss} and patch "
                f"them directly into result/{slug}.json (fallback ladder rung 4, "
                "disclose 'patched by fallback'); or re-dispatch the worker with "
                "this targeted hint"), False, True
    if "parse" in kinds:
        return (f"result/{slug}.json is not valid JSON - re-dispatch the worker; "
                "instruct it to output raw JSON only, no prose or code fence"), True, False
    if any(i.startswith("worker_error: invalid_output") for i in issues):
        return ("model failed to produce usable JSON - re-dispatch on the "
                "escalate_to tier; instruct raw JSON-only output"), True, False
    if "long" in kinds:
        return (f"field(s) {longs} exceed the {max_len}-char limit - re-dispatch "
                f"the worker; instruct it to compress {longs} to terse values "
                f"<= {max_len} chars"), True, False
    if "worker" in kinds:
        return ("worker reported an error - work the fallback ladder: alternate "
                "source type first, then alternate fetch engine; do not escalate "
                "model tier, a stronger model cannot unblock a source"), False, False
    if "url" in kinds:
        return ("source URL malformed - re-dispatch the worker with the hint to "
                "re-verify and rewrite source URLs in https:// form"), False, False
    return ("re-dispatch the worker with this defect list"), False, False


def main():
    ap = argparse.ArgumentParser(description="WideHive merge & validate")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--required-fields", default=None,
                    help="comma-separated field names; defaults to plan.json fields")
    ap.add_argument("--max-field-len", type=int, default=4000)
    args = ap.parse_args()

    run = Path(args.run_dir)
    if not run.is_dir():
        print(json.dumps({"error": f"run dir not found: {run}"}, ensure_ascii=False))
        sys.exit(1)

    plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
    targets = json.loads((run / "targets.json").read_text(encoding="utf-8"))
    if args.required_fields:
        fields = [f.strip() for f in args.required_fields.split(",") if f.strip()]
    else:
        fields = plan.get("fields", [])
    scenario = plan.get("scenario", "custom")

    result_dir = run / "result"
    defects, rows, records, missing = [], [], [], []
    clean = 0

    for t in targets:
        slug = t.get("slug", "")
        if not slug:
            defects.append({"slug": "?", "issues": ["target_without_slug"],
                            "retry_hint": "target has no slug - fix targets.json "
                                          "before any retry", "escalate": False,
                            "patchable": False})
            continue
        f = result_dir / f"{slug}.json"
        if not f.exists():
            missing.append(slug)
            hint, esc, patch = prescribe(slug, [], True, args.max_field_len)
            defects.append({"slug": slug, "issues": ["missing_result_file"],
                            "retry_hint": hint, "escalate": esc, "patchable": patch})
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            hint, esc, patch = prescribe(slug, [f"json_parse_error: {e}"], False,
                                         args.max_field_len)
            defects.append({"slug": slug, "issues": [f"json_parse_error: {e}"],
                            "retry_hint": hint, "escalate": esc, "patchable": patch})
            continue

        issues = []
        fd = data.get("fields") if isinstance(data.get("fields"), dict) else {}
        if data.get("error"):
            issues.append(f"worker_error: {data.get('error')}")
        for k in fields:
            v = fd.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                issues.append(f"missing_field: {k}")
            elif isinstance(v, str) and len(v) > args.max_field_len:
                issues.append(f"field_too_long: {k} ({len(v)} chars)")
        for s in data.get("sources") or []:
            u = s.get("url") if isinstance(s, dict) else None
            if u and not URL_RE.match(str(u)):
                issues.append(f"bad_source_url: {u}")
        if issues:
            hint, esc, patch = prescribe(slug, issues, False, args.max_field_len)
            defects.append({"slug": slug, "issues": issues,
                            "retry_hint": hint, "escalate": esc, "patchable": patch})
        else:
            clean += 1

        row = {"slug": slug,
               "name": t.get("name", data.get("target", "")),
               "scenario": scenario}
        for k in fields:
            v = fd.get(k)
            if isinstance(v, (list, dict)):
                row[k] = json.dumps(v, ensure_ascii=False)
            else:
                row[k] = "" if v is None else v
        row["n_sources"] = len(data.get("sources") or [])
        rows.append(row)
        records.append(data)

    retry_queue = {"patch_first": [], "retry": [], "escalate": []}
    for d in defects:
        if d.get("escalate"):
            retry_queue["escalate"].append(d["slug"])
        elif d.get("patchable"):
            retry_queue["patch_first"].append(d["slug"])
        else:
            retry_queue["retry"].append(d["slug"])

    out_json = run / "merged.json"
    out_csv = run / "merged.csv"
    out_json.write_text(
        json.dumps({"scenario": scenario, "fields": fields, "records": records},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")
    if rows:
        cols = ["slug", "name", "scenario"] + fields + ["n_sources"]
        with out_csv.open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow(r)

    report = {
        "total_targets": len(targets),
        "with_results": len(rows),
        "ok": clean,
        "missing_files": missing,
        "defects": defects,
        "retry_queue": retry_queue,
        "merged_csv": str(out_csv) if rows else None,
        "merged_json": str(out_json),
        "verdict": ("PASS" if rows and not defects and not missing else "NEEDS_RETRY"),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
