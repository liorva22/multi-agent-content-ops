"""Run the pipeline on one or more PRD files.

    MOCK_MODE=1 python -m contentops.run examples/prds/*.md
    python -m contentops.run examples/prds/smart-inbox.md     # live Claude agents

Logs every step to Postgres when DATABASE_URL is set, writes posts to results/, and prints a per-run summary.
"""

import argparse
import json
import os
from pathlib import Path

from .agents import ClaudeAgents, MockAgents
from .llm import ROOT, is_mock, load_config
from .orchestrator import run_pipeline


def execute(name: str, prd: str, cfg: dict, conn=None) -> dict:
    agents = MockAgents(cfg) if is_mock() else ClaudeAgents(cfg)
    steps: list[dict] = []
    run_id, db_log = None, None
    if conn is not None:
        from . import db

        run_id = db.start_run(conn, name, prd, "mock" if is_mock() else "live")
        db_log = db.step_logger(conn, run_id)

    def log(s):
        steps.append(s)
        if db_log:
            db_log(s)

    result = run_pipeline(prd, agents, cfg, log)
    if conn is not None:
        from . import db

        db.finish_run(conn, run_id, result)
    return {"run_id": run_id, "name": name, "result": result, "steps": steps}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("prds", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    args = ap.parse_args(argv)

    cfg = load_config()
    conn = None
    if os.getenv("DATABASE_URL"):
        from .db import connect

        conn = connect()
    args.out.mkdir(parents=True, exist_ok=True)
    summary = []
    for path in args.prds:
        run = execute(path.stem, path.read_text(encoding="utf-8"), cfg, conn)
        r = run["result"]
        if r.get("final"):
            (args.out / f"{path.stem}.md").write_text(r["final"], encoding="utf-8")
        (args.out / f"{path.stem}.steps.json").write_text(json.dumps(run["steps"], indent=2, default=str), encoding="utf-8")
        row = {
            "prd": path.stem,
            "status": r["status"],
            "retries": r["retries"],
            "steps": len(run["steps"]),
            "tokens": sum(s["input_tokens"] + s["output_tokens"] for s in run["steps"]),
            "cost_usd": round(sum(s["cost_usd"] for s in run["steps"]), 6),
            "rubric_score": r["rubric"]["score"] if r.get("rubric") else None,
            "rubric": r.get("rubric"),
            "per_agent": {},
        }
        for s in run["steps"]:
            a = row["per_agent"].setdefault(s["agent"], {"calls": 0, "tokens": 0, "cost_usd": 0.0, "latency_ms": 0.0})
            a["calls"] += 1
            a["tokens"] += s["input_tokens"] + s["output_tokens"]
            a["cost_usd"] += s["cost_usd"]
            a["latency_ms"] += s["latency_ms"]
        summary.append(row)
        print(f"{path.stem}: {r['status']} | retries={r['retries']} | rubric={row['rubric_score']} | ${row['cost_usd']}")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    main()
