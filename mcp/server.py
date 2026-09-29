#!/usr/bin/env python3
"""WideHive MCP server - exposes the WideHive pipeline scripts as MCP tools.

Run (stdio, default):   python server.py
Run (HTTP/SSE):         python server.py --transport sse --port 8808

Tools:
  merge_results(run_dir, required_fields?)            merge + validate, verdict JSON
  diff_results(baseline, current, compare_fields?)    watch diff report
  build_corpus(runs_root, out?)                       corpus.jsonl + index
  build_dashboard(merged, out?, title?)               self-contained dashboard HTML
Resources:
  widehive://spec/SKILL.md                        the five-stage orchestration spec
  widehive://spec/scenarios/financial-filings.md  financial-filings scenario pack
  widehive://spec/scenarios/tech-selection.md     tech-selection scenario pack
Prompts:
  widehive_orchestration()  full orchestration spec text (for platforms without resource support)

Scripts are resolved relative to this file: ../skill/scripts/ (override with
the WIDEHIVE_SCRIPTS_DIR environment variable).

Compatible with mcp 1.x (FastMCP) and 2.x (MCPServer).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

try:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server
except ModuleNotFoundError:  # mcp 2.x renamed FastMCP -> MCPServer
    from mcp.server.mcpserver import MCPServer as _Server

SERVER_DIR = Path(__file__).resolve().parent
_DEFAULT_SCRIPTS = SERVER_DIR.parent / "skill" / "scripts"
SCRIPTS = Path(os.environ.get("WIDEHIVE_SCRIPTS_DIR", str(_DEFAULT_SCRIPTS))).resolve()
REPO_ROOT = SCRIPTS.parent.parent

mcp = _Server(
    "widehive",
    instructions=(
        "WideHive: Wide Research orchestration helpers. Use merge_results after a "
        "fan-out run to validate and aggregate; diff_results for watch-mode deltas; "
        "build_corpus / build_dashboard for knowledge-base and reporting. Read the "
        "spec resource for the full five-stage orchestration rules."
    ),
)


def _run(script: str, args: list) -> str:
    cmd = [sys.executable, str(SCRIPTS / script)] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, encoding="utf-8")
    out = r.stdout or ""
    if r.stderr and r.stderr.strip():
        out += "\n[stderr] " + r.stderr.strip()
    return out if out.strip() else "(no output)"


@mcp.tool()
def merge_results(run_dir: str, required_fields: str = "") -> str:
    """Merge & validate a WideHive run (zero LLM). Returns a PASS/NEEDS_RETRY verdict JSON with per-object defects."""
    args = ["--run-dir", run_dir]
    if required_fields.strip():
        args += ["--required-fields", required_fields.strip()]
    return _run("merge_results.py", args)


@mcp.tool()
def diff_results(baseline: str, current: str, compare_fields: str = "") -> str:
    """Diff a current run against a baseline run (watch mode, zero LLM). Returns summary + per-field changes."""
    args = ["--baseline", baseline, "--current", current]
    if compare_fields.strip():
        args += ["--compare-fields", compare_fields.strip()]
    return _run("diff_results.py", args)


@mcp.tool()
def build_corpus(runs_root: str, out: str = "") -> str:
    """Consolidate finished runs into a queryable corpus (corpus.jsonl + index). Returns stats JSON."""
    args = ["--runs-root", runs_root]
    if out.strip():
        args += ["--out", out]
    return _run("build_corpus.py", args)


@mcp.tool()
def build_dashboard(merged: str, out: str = "", title: str = "") -> str:
    """Render merged.json into a self-contained interactive dashboard HTML (search/sort/drill-down)."""
    args = ["--merged", merged]
    if out.strip():
        args += ["--out", out]
    if title.strip():
        args += ["--title", title.strip()]
    return _run("build_dashboard.py", args)


@mcp.resource("widehive://spec/SKILL.md")
def spec() -> str:
    """The WideHive five-stage orchestration spec (iron rules, stages, templates)."""
    return (REPO_ROOT / "skill" / "SKILL.md").read_text(encoding="utf-8")


@mcp.resource("widehive://spec/scenarios/financial-filings.md")
def scenario_financial() -> str:
    """The financial-filings scenario pack (fields, worker prompt variant, report layout, pitfalls)."""
    return (REPO_ROOT / "scenarios" / "financial-filings.md").read_text(encoding="utf-8")


@mcp.resource("widehive://spec/scenarios/tech-selection.md")
def scenario_tech() -> str:
    """The tech-selection scenario pack (fields, maintenance_status enum, source ladder, license-risk pitfalls)."""
    return (REPO_ROOT / "scenarios" / "tech-selection.md").read_text(encoding="utf-8")


@mcp.prompt()
def widehive_orchestration() -> str:
    """Full WideHive orchestration spec, for agents that can spawn isolated sub-agents."""
    return (REPO_ROOT / "skill" / "SKILL.md").read_text(encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--transport", default="stdio", choices=["stdio", "sse"])
    ap.add_argument("--port", type=int, default=8808)
    a = ap.parse_args()
    if a.transport == "sse":
        mcp.run(transport="sse", port=a.port)
    else:
        mcp.run()
