#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WideHive Stage 3 driver - parallel CLI fan-out for headless-capable harnesses.

Spawns N concurrent headless CLI workers (CodeBuddy / Claude Code / Codex CLI),
one worker per object, each writing result/<slug>.json. This is the parallel
answer to harnesses whose GUI has no sub-agent spawning (WorkBuddy, Trae):
the orchestrator used to process objects serially; this driver restores
fan-out at the process level.

NOT a zero-LLM tool: every worker costs tokens. Run it from a shell-capable
orchestrator, not via the widehive MCP server.

Usage (first full pass):
  python fanout_cli.py --run-dir <run_dir> [--concurrency 4]

Usage (targeted retry, from the merge verdict - only defective objects, with
the merge prescription injected into each retry prompt, escalated objects on
the escalate_to model):
  python merge_results.py --run-dir <run_dir> > verdict.json
  python fanout_cli.py --run-dir <run_dir> --hints verdict.json \
      --slugs "$(slugs from retry_queue)" --concurrency 4

Model tiering: --model overrides plan.json "models": {"worker": ...};
slugs escalated via --escalate-slugs or a hints file (defects with
"escalate": true) run on plan.json "models": {"escalate_to": ...} or
--escalate-model.

Checkpoint resume: slugs with an existing result/*.json are skipped unless
--force. Each worker outcome is appended to <run_dir>/fanout_log.jsonl.
If a worker cannot write files, its stdout JSON is captured and written by
this driver (marked "patched_by": "stdout_capture").
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

PROMPT_TEMPLATE = """You are a Wide Research single-object worker. Handle ONLY this one object; do not expand scope.

Object: {name} ({identifier})
Task:
1. Fetch first-hand info about this object. Prefer official / authoritative sources. Use your web tools (dedicated web-open tools first, built-in web fetch as fallback). At most 3 searches/fetches.
2. Extract strictly per the field template. If a value cannot be verified, write null - never guess. Fields:
{fields}
3. Write the result file (UTF-8) to: {result_path}
   Structure: {{"target":"{name}","fields":{{...}},"sources":[{{"title":"...","url":"..."}}],"fetched_at":"{today}"}}
4. If you cannot write files, output the same JSON verbatim as your final message instead.
{hint_block}
No long prose. Write the file and finish."""

# Per-CLI base command + permission args + model flag. Any of these can be
# overridden with --cli-command / --cli-arg / --model-flag.
CODEBUDDY_JS_CANDIDATES = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "WorkBuddy" / "resources"
        / "app.asar.unpacked" / "cli" / "dist" / "codebuddy-headless.js",
]


def split_cmd(s):
    """shlex that survives Windows paths (backslashes are not escapes there)."""
    if os.name == "nt":
        return [t.strip('"') for t in shlex.split(s, posix=False)]
    return shlex.split(s)


def resolve_cli(name):
    """Return (cmd_list, model_flag, permission_args) for a CLI profile, or None."""
    if name == "codebuddy":
        exe = shutil.which("codebuddy") or shutil.which("cbc")
        if exe:
            return [exe], "--model", ["--permission-mode", "acceptEdits"]
        for js in CODEBUDDY_JS_CANDIDATES:
            if js.is_file() and shutil.which("node"):
                return ["node", str(js)], "--model", ["--permission-mode", "acceptEdits"]
        return None
    if name == "claude":
        exe = shutil.which("claude")
        if exe:
            return [exe, "-p"], "--model", \
                ["--allowedTools", "WebSearch,WebFetch,Write,Read,Edit"]
        return None
    if name == "codex":
        exe = shutil.which("codex")
        if exe:
            return [exe, "exec", "--full-auto"], "-m", []
        return None
    return None


def detect_cli():
    for name in ("codebuddy", "claude", "codex"):
        r = resolve_cli(name)
        if r:
            return name, r
    return None, None


def build_prompt(t, fields, result_path, today, hint=None):
    fl = "\n".join(f"   - {f}" for f in fields)
    hint_block = ""
    if hint:
        hint_block = ("PREVIOUS ATTEMPT DEFECT (fix ONLY this; keep the rest of "
                      f"the existing file if it is valid):\n   - {hint}\n")
    ident = t.get("url") or t.get("identifier") or t.get("name", "")
    return PROMPT_TEMPLATE.format(name=t.get("name", ""), identifier=ident,
                                  fields=fl, result_path=result_path,
                                  today=today, hint_block=hint_block)


def capture_stdout_json(stdout):
    """Extract a worker-result JSON object from stdout (file-write fallback)."""
    if not stdout:
        return None
    try:
        obj = json.loads(stdout)
    except Exception:
        m = re.search(r"\{.*\}", stdout, re.S)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except Exception:
            return None
    if isinstance(obj, dict) and isinstance(obj.get("fields"), dict):
        return obj
    return None


def main():
    ap = argparse.ArgumentParser(description="WideHive parallel CLI fan-out")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--cli", default="auto",
                    help="auto | codebuddy | claude | codex")
    ap.add_argument("--cli-command", default=None,
                    help="full worker command override, e.g. "
                         "'node <path>/codebuddy-headless.js -p' (prompt is "
                         "appended as the last argument)")
    ap.add_argument("--model", default=None,
                    help="worker model id (default: plan.json models.worker)")
    ap.add_argument("--model-flag", default=None,
                    help="flag preceding the model id (default per CLI)")
    ap.add_argument("--escalate-model", default=None,
                    help="model for escalated slugs (default: plan models.escalate_to)")
    ap.add_argument("--escalate-slugs", default="",
                    help="comma-separated slugs to run on the escalated model")
    ap.add_argument("--slugs", default="",
                    help="comma-separated slugs to dispatch (default: all pending)")
    ap.add_argument("--hints", default=None,
                    help="merge verdict JSON file ({defects:[...]}) or a "
                         "{slug: hint} dict; injects retry_hint into the "
                         "worker prompt and escalates defects flagged escalate")
    ap.add_argument("--timeout", type=int, default=900,
                    help="per-worker timeout in seconds (default 900)")
    ap.add_argument("--force", action="store_true",
                    help="re-dispatch even if result/<slug>.json exists")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the dispatch plan and exit")
    ap.add_argument("--cli-arg", action="append", default=[],
                    help="extra argument appended to each worker command "
                         "(repeatable, placed before the prompt)")
    args = ap.parse_args()

    run = Path(args.run_dir)
    plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
    targets = json.loads((run / "targets.json").read_text(encoding="utf-8"))
    fields = plan.get("fields", [])
    models = plan.get("models", {})
    result_dir = run / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()

    # CLI resolution
    if args.cli_command:
        base_cmd = split_cmd(args.cli_command)
        model_flag = args.model_flag or "--model"
        perm_args = []
        cli_name = "custom"
    else:
        name = args.cli
        if name == "auto":
            cli_name, resolved = detect_cli()
        else:
            cli_name, resolved = name, resolve_cli(name)
        if not resolved:
            print(json.dumps({"error": "no headless CLI found; install codebuddy/"
                                       "claude/codex or pass --cli-command"},
                             ensure_ascii=False))
            sys.exit(1)
        base_cmd, model_flag, perm_args = resolved
        model_flag = args.model_flag or model_flag
    extra_args = [a for arg in args.cli_arg for a in split_cmd(arg)]

    # Hints / escalation sets
    hints, escalate_slugs = {}, set(args.escalate_slugs.split(",")) - {""}
    if args.hints:
        src = json.loads(Path(args.hints).read_text(encoding="utf-8"))
        if isinstance(src, dict) and "defects" in src:  # merge verdict report
            hints = {d["slug"]: d.get("retry_hint", "") for d in src["defects"]
                     if d.get("retry_hint")}
            escalate_slugs |= {d["slug"] for d in src["defects"]
                               if d.get("escalate")}
        elif isinstance(src, list):  # raw defects array
            hints = {d["slug"]: d.get("retry_hint", "") for d in src
                     if d.get("retry_hint")}
            escalate_slugs |= {d["slug"] for d in src if d.get("escalate")}
        elif isinstance(src, dict):  # plain {slug: hint}
            hints = src
        target_slugs = {t.get("slug") for t in targets}
        hints = {k: v for k, v in hints.items() if k in target_slugs}

    # Pending set (checkpoint resume)
    only = set(args.slugs.split(",")) - {""}
    pending, skipped = [], []
    for t in targets:
        slug = t.get("slug", "")
        if not slug or (only and slug not in only):
            continue
        if not args.force and (result_dir / f"{slug}.json").exists():
            skipped.append(slug)
            continue
        pending.append(t)

    esc_model = args.escalate_model or models.get("escalate_to")
    base_model = args.model or models.get("worker")

    def command_for(slug):
        cmd = list(base_cmd)
        m = esc_model if (slug in escalate_slugs and esc_model) else base_model
        if m:
            cmd += [model_flag, m]
        cmd += perm_args + extra_args
        return cmd, m

    jobs = []
    for t in pending:
        slug = t["slug"]
        cmd, m = command_for(slug)
        rp = str((result_dir / f"{slug}.json").resolve())
        prompt = build_prompt(t, fields, rp, today, hint=hints.get(slug))
        jobs.append({"slug": slug, "cmd": cmd + [prompt], "model": m,
                     "result_path": rp})

    plan_view = {"cli": cli_name if not args.cli_command else "custom",
                 "concurrency": args.concurrency,
                 "base_model": base_model, "escalate_model": esc_model,
                 "escalated_slugs": sorted(s for s in escalate_slugs
                                           if s in {j["slug"] for j in jobs}),
                 "dispatched": len(jobs), "skipped_existing": skipped,
                 "jobs": [{"slug": j["slug"], "model": j["model"],
                           "cmd_head": " ".join(j["cmd"][:-1])[:160]}
                          for j in jobs]}
    if args.dry_run:
        print(json.dumps(plan_view, ensure_ascii=False, indent=2))
        return

    log_path = run / "fanout_log.jsonl"
    lock_print = threading.Lock()

    def run_one(job):
        t0 = time.time()
        entry = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                 "slug": job["slug"], "model": job["model"]}
        status, err, patched = "ok", None, None
        code = None
        try:
            r = subprocess.run(job["cmd"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               stdin=subprocess.DEVNULL, timeout=args.timeout)
            code = r.returncode
            if r.stderr and r.stderr.strip():
                entry["stderr_tail"] = r.stderr.strip()[-400:]
        except subprocess.TimeoutExpired:
            status = "timeout"
        except OSError as e:
            status = "spawn_error"
            err = str(e)

        rf = Path(job["result_path"])
        if status == "ok":
            if rf.is_file():
                try:
                    json.loads(rf.read_text(encoding="utf-8"))
                except Exception:
                    status, err = "invalid_output", "result file is not valid JSON"
            else:
                obj = capture_stdout_json(r.stdout)
                if obj:
                    obj.setdefault("patched_by", "stdout_capture")
                    rf.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
                    patched = "stdout_capture"
                else:
                    status, err = "invalid_output", \
                        "no result file and no parsable JSON on stdout"
        entry.update({"status": status, "exit_code": code,
                      "duration_s": round(time.time() - t0, 1),
                      "result_file": str(rf) if rf.is_file() else None,
                      "patched_by": patched, "error": err})
        with lock_print:
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    t_start = time.time()
    outcomes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(run_one, j): j for j in jobs}
        for fut in concurrent.futures.as_completed(futs):
            outcomes.append(fut.result())

    ok_n = sum(1 for o in outcomes if o["status"] == "ok")
    summary = {
        "cli": plan_view["cli"], "concurrency": args.concurrency,
        "dispatched": len(jobs), "ok": ok_n,
        "failed": [o["slug"] for o in outcomes if o["status"] != "ok"],
        "skipped_existing": skipped,
        "escalated_slugs": plan_view["escalated_slugs"],
        "patched_by_stdout": [o["slug"] for o in outcomes if o.get("patched_by")],
        "wall_time_s": round(time.time() - t_start, 1),
        "log": str(log_path),
        "next": "python merge_results.py --run-dir %s" % run,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    sys.exit(0 if ok_n == len(jobs) and len(jobs) > 0 else 1)


if __name__ == "__main__":
    main()
