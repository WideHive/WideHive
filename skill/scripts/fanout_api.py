#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WideHive Stage 3 driver - thin API workers (no agent platform required).

Same orchestration contract as fanout_cli.py (targets/plan/result, checkpoint
resume, retry prescriptions, escalate routing, fanout_log.jsonl) but the
worker is NOT an agent: this script fetches pages itself and calls any
OpenAI-compatible chat API for extraction only. No platform login, no
per-worker agent overhead, free choice of provider/model.

Fetch ladder (mirrors the tech-selection scenario pack):
  1. target `url` known            -> fetch directly (up to --max-fetches pages)
  2. no url, search provider set   -> search, fetch top 2 hits
  3. zero successful fetches       -> skip the LLM call, record fetch_failed
     (prescription routes the object to an agent-worker / fallback ladder)

Sources are built by the script from its own fetch records - provenance the
merge step can trust by construction, not by worker honesty.

Config (flags win over env):
  --api-base / --api-key   env: WIDEHIVE_API_BASE, WIDEHIVE_API_KEY
                           (also reads OPENAI_BASE_URL, OPENAI_API_KEY)
  --model / --escalate-model  default from plan.json models.worker / escalate_to
  --search-provider tavily|bocha|none   env: TAVILY_API_KEY / BOCHA_API_KEY
                                        (--search-base-url overrides the endpoint, for tests/self-host)

Dependencies: stdlib only. If `trafilatura` is installed it upgrades HTML
text extraction; otherwise a built-in tag-stripping extractor is used.
Binary content types (PDF etc.) are not handled here - they are recorded as
fetch failures and belong to the agent-worker ladder.

Not a zero-LLM tool. Run from a shell-capable orchestrator.
"""
import argparse
import concurrent.futures
import datetime
import gzip
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

UA = "WideHive-thin-worker/1.0 (+https://github.com/WideHive/WideHive)"

SYSTEM_PROMPT = (
    "You are a Wide Research single-object extraction worker. You receive the "
    "raw text of one or more fetched pages for EXACTLY ONE object. Extract the "
    "requested fields strictly from that text. If a value cannot be verified "
    "from the provided text, write null - never guess, never use prior "
    "knowledge. Output ONLY one raw JSON object, no prose, no code fences: "
    '{"target": "<object name>", "fields": {"<field>": <value or null>, ...}}'
)

SEARCH_ENDPOINTS = {
    "tavily": "https://api.tavily.com/search",
    "bocha": "https://api.bochaai.com/v1/web-search",
}


class FetchError(Exception):
    pass


class _TextExtractor(HTMLParser):
    _BLOCK = {"p", "div", "section", "article", "li", "tr", "h1", "h2", "h3",
              "h4", "h5", "h6", "br", "table", "ul", "ol", "header", "footer",
              "nav", "blockquote", "pre"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        elif tag in self._BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip = max(0, self._skip - 1)
        elif tag in self._BLOCK:
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip and data.strip():
            self._parts.append(data)

    def text(self):
        raw = "".join(self._parts)
        return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", raw)).strip()


def _fallback_extract(html):
    ex = _TextExtractor()
    try:
        ex.feed(html)
        return ex.text()
    except Exception:
        cleaned = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
        return unescape(re.sub(r"(?s)<[^>]+>", " ", cleaned)).strip()


def extract_text(html):
    """trafilatura if available (better main-content focus), else fallback."""
    try:
        import trafilatura  # optional
        txt = trafilatura.extract(html, include_comments=False) or ""
        return txt.strip() or _fallback_extract(html)
    except ImportError:
        return _fallback_extract(html)


def fetch_url(url, timeout, max_chars):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/json,*/*;q=0.8",
        "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                body = gzip.GzipFile(fileobj=io.BytesIO(body)).read()
            ctype = resp.headers.get("Content-Type", "").split(";")[0].strip()
            final_url = resp.geturl()
    except Exception as e:
        raise FetchError(f"{type(e).__name__}: {e}") from e
    if ctype.startswith("image/") or ctype in ("application/pdf",):
        raise FetchError(f"unsupported_content_type: {ctype}")
    text = body.decode("utf-8", errors="replace")
    if ctype == "application/json" or url.rstrip("/").endswith(".json"):
        return text[:max_chars], final_url
    if "html" in ctype or "<html" in text[:1000].lower():
        title_m = re.search(r"(?is)<title[^>]*>(.*?)</title>", text)
        title = unescape(title_m.group(1)).strip() if title_m else ""
        return extract_text(text)[:max_chars], final_url
    return text[:max_chars], final_url


def search_web(provider, key, query, base_url, timeout):
    if provider == "tavily":
        payload = json.dumps({"api_key": key, "query": query,
                              "max_results": 3}).encode()
    elif provider == "bocha":
        payload = json.dumps({"query": query, "count": 3,
                              "summary": True}).encode()
    else:
        return []
    req = urllib.request.Request(base_url or SEARCH_ENDPOINTS[provider],
                                 data=payload, method="POST",
                                 headers={"User-Agent": UA,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return []
    if provider == "tavily":
        return [{"url": r.get("url"), "title": r.get("title", "")}
                for r in data.get("results", []) if r.get("url")]
    webpages = (data.get("data") or {}).get("webPages", {}).get("value", [])
    return [{"url": r.get("url"), "title": r.get("name", "")}
            for r in webpages if r.get("url")]


def call_llm(base, key, model, user_prompt, timeout, json_mode=True):
    """One chat-completions call; falls back once without json mode on 400."""
    body = {"model": model, "temperature": 0,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": user_prompt}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    last_err = None
    for attempt in (True, False):
        payload = json.dumps(body).encode()
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions", data=payload, method="POST",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return data["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            last_err = f"HTTP {e.code}: {detail}"
            if e.code == 400 and json_mode and attempt:
                body.pop("response_format", None)  # provider may reject json mode
                continue
            raise RuntimeError(f"llm_error {last_err}") from e
        except Exception as e:
            raise RuntimeError(f"llm_error {type(e).__name__}: {e}") from e
    raise RuntimeError(f"llm_error {last_err}")


def parse_llm_json(content):
    try:
        obj = json.loads(content)
    except Exception:
        m = re.search(r"\{.*\}", content or "", re.S)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except Exception:
            return None
    return obj if isinstance(obj, dict) and isinstance(obj.get("fields"), dict) else None


def build_user_prompt(t, fields, pages, hint=None):
    src_blocks = "\n\n".join(
        f"[SOURCE {i + 1}] url: {p['url']}\n{p['text']}"
        for i, p in enumerate(pages))
    field_lines = "\n".join(f"- {f}" for f in fields)
    hint_block = ""
    if hint:
        hint_block = ("PREVIOUS ATTEMPT DEFECT (fix ONLY this; write null only "
                      f"where the sources truly do not say):\n   - {hint}\n")
    return (f"Object: {t.get('name', '')}\nFields to extract:\n{field_lines}\n\n"
            f"{hint_block}Fetched page text:\n\n{src_blocks}")


def main():
    ap = argparse.ArgumentParser(description="WideHive thin API fan-out")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--api-base", default=os.environ.get("WIDEHIVE_API_BASE")
                    or os.environ.get("OPENAI_BASE_URL"))
    ap.add_argument("--api-key", default=os.environ.get("WIDEHIVE_API_KEY")
                    or os.environ.get("OPENAI_API_KEY"))
    ap.add_argument("--model", default=None)
    ap.add_argument("--escalate-model", default=None)
    ap.add_argument("--escalate-slugs", default="")
    ap.add_argument("--slugs", default="")
    ap.add_argument("--hints", default=None,
                    help="merge verdict JSON ({defects:[...]}) or {slug: hint} dict")
    ap.add_argument("--search-provider", default="none",
                    choices=["none", "tavily", "bocha"])
    ap.add_argument("--search-base-url", default=None)
    ap.add_argument("--max-fetches", type=int, default=3)
    ap.add_argument("--max-page-chars", type=int, default=15000)
    ap.add_argument("--llm-timeout", type=int, default=120)
    ap.add_argument("--fetch-timeout", type=int, default=30)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.api_base or not args.api_key:
        print(json.dumps({"error": "missing API credentials: pass --api-base/"
                                   "--api-key or set WIDEHIVE_API_BASE/"
                                   "WIDEHIVE_API_KEY"}, ensure_ascii=False))
        sys.exit(1)
    search_key = {"tavily": os.environ.get("TAVILY_API_KEY"),
                  "bocha": os.environ.get("BOCHA_API_KEY")}.get(
                      args.search_provider)
    if args.search_provider != "none" and not search_key and not args.search_base_url:
        print(json.dumps({"error": f"--search-provider {args.search_provider} "
                                   "needs its API key env var"}, ensure_ascii=False))
        sys.exit(1)

    run = Path(args.run_dir)
    plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
    targets = json.loads((run / "targets.json").read_text(encoding="utf-8"))
    fields = plan.get("fields", [])
    models = plan.get("models", {})
    result_dir = run / "result"
    today = datetime.date.today().isoformat()
    base_model = args.model or models.get("worker")
    esc_model = args.escalate_model or models.get("escalate_to")

    # hints / escalation (same contract as fanout_cli.py)
    hints, escalate_slugs = {}, set(args.escalate_slugs.split(",")) - {""}
    if args.hints:
        src = json.loads(Path(args.hints).read_text(encoding="utf-8"))
        if isinstance(src, dict) and "defects" in src:
            hints = {d["slug"]: d.get("retry_hint", "") for d in src["defects"]
                     if d.get("retry_hint")}
            escalate_slugs |= {d["slug"] for d in src["defects"] if d.get("escalate")}
        elif isinstance(src, list):
            hints = {d["slug"]: d.get("retry_hint", "") for d in src
                     if d.get("retry_hint")}
            escalate_slugs |= {d["slug"] for d in src if d.get("escalate")}
        else:
            hints = src
        target_slugs = {t.get("slug") for t in targets}
        hints = {k: v for k, v in hints.items() if k in target_slugs}

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

    def fetch_plan_for(t):
        """Return ('url'|'search', [urls to try]) within --max-fetches."""
        url = t.get("url")
        if url:
            return "url", [url]
        if args.search_provider != "none":
            hits = search_web(args.search_provider, search_key,
                              f"{t.get('name', '')} {t.get('owner', '')}".strip(),
                              args.search_base_url, args.fetch_timeout)
            return "search", [h["url"] for h in hits[:2]]
        return "none", []

    jobs = []
    for t in pending:
        slug = t["slug"]
        m = esc_model if (slug in escalate_slugs and esc_model) else base_model
        mode, urls = fetch_plan_for(t)
        jobs.append({"slug": slug, "target": t, "model": m,
                     "mode": mode, "urls": urls})

    plan_view = {"executor": "thin-api", "concurrency": args.concurrency,
                 "api_base": args.api_base, "base_model": base_model,
                 "escalate_model": esc_model,
                 "escalated_slugs": sorted(s for s in escalate_slugs
                                           if s in {j["slug"] for j in jobs}),
                 "search_provider": args.search_provider,
                 "dispatched": len(jobs), "skipped_existing": skipped,
                 "jobs": [{"slug": j["slug"], "model": j["model"],
                           "fetch_mode": j["mode"],
                           "urls": j["urls"][:3]} for j in jobs]}
    if args.dry_run:
        print(json.dumps(plan_view, ensure_ascii=False, indent=2))
        return

    result_dir.mkdir(parents=True, exist_ok=True)
    log_path = run / "fanout_log.jsonl"
    lock = threading.Lock()

    def run_one(job):
        t0 = time.time()
        slug = job["slug"]
        entry = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                 "slug": slug, "model": job["model"], "executor": "thin-api"}
        pages, fetched_urls, status, err = [], [], "ok", None

        for url in job["urls"][:args.max_fetches]:
            try:
                text, final_url = fetch_url(url, args.fetch_timeout,
                                            args.max_page_chars)
                pages.append({"url": final_url, "title": "",
                              "text": text})
                fetched_urls.append(final_url)
            except FetchError as e:
                entry.setdefault("fetch_errors", []).append(
                    {"url": url, "error": str(e)})

        if not pages:
            status, err = "fetch_failed", "no page could be fetched"
        else:
            prompt = build_user_prompt(job["target"], fields, pages,
                                       hint=hints.get(slug))
            try:
                content = call_llm(args.api_base, args.api_key, job["model"],
                                   prompt, args.llm_timeout)
                obj = parse_llm_json(content)
                if obj is None:
                    status, err = "invalid_output", "LLM output is not usable JSON"
                else:
                    record = {"target": job["target"].get("name", ""),
                              "fields": obj.get("fields", {}),
                              "sources": [{"title": "", "url": u}
                                          for u in fetched_urls],
                              "fetched_at": today,
                              "worker": "thin-api"}
                    if slug in escalate_slugs and esc_model:
                        record["escalated"] = True
                    (result_dir / f"{slug}.json").write_text(
                        json.dumps(record, ensure_ascii=False, indent=2),
                        encoding="utf-8")
            except RuntimeError as e:
                status, err = "llm_error", str(e)

        if status != "ok":
            # disclose every failure as an error record so the merge verdict
            # routes it and checkpoint re-runs skip it (spec: never silently
            # drop an object; retries re-dispatch with --force)
            (result_dir / f"{slug}.json").write_text(
                json.dumps({"target": job["target"].get("name", ""),
                            "fields": {},
                            "error": status,
                            "sources": [{"title": "", "url": u}
                                        for u in fetched_urls],
                            "fetched_at": today, "worker": "thin-api"},
                           ensure_ascii=False, indent=2),
                encoding="utf-8")

        entry.update({"status": status, "duration_s": round(time.time() - t0, 1),
                      "fetched_urls": fetched_urls,
                      "pages_chars": sum(len(p["text"]) for p in pages),
                      "result_file": str(result_dir / f"{slug}.json")
                      if status == "ok" else None, "error": err})
        with lock:
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
    summary = {"executor": "thin-api", "concurrency": args.concurrency,
               "dispatched": len(jobs), "ok": ok_n,
               "failed": [{"slug": o["slug"], "status": o["status"]}
                          for o in outcomes if o["status"] != "ok"],
               "skipped_existing": skipped,
               "escalated_slugs": plan_view["escalated_slugs"],
               "wall_time_s": round(time.time() - t_start, 1),
               "log": str(log_path),
               "next": "python merge_results.py --run-dir %s" % run}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    sys.exit(0 if ok_n == len(jobs) and len(jobs) > 0 else 1)


if __name__ == "__main__":
    main()
