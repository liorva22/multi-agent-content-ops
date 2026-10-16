"""Hand-rolled state machine: research -> write -> fact_check -> (rollback to write | polish) -> score.

Each transition is one row in `steps`; see docs/DECISIONS.md for why this isn't LangGraph.
"""

import json
import time

from .checks import score_post


def run_pipeline(prd: str, agents, cfg: dict, log=lambda step: None) -> dict:
    """`log(step)` is called after every step (the Postgres logger in production). Returns the run outcome."""
    state = {"facts": None, "draft": None, "feedback": None, "attempt": 0, "final": None, "rubric": None}
    step, seq, retries = "research", 0, 0
    t_run = time.perf_counter()

    while step not in ("done", "needs_review"):
        seq += 1
        attempt = state["attempt"] + 1 if step == "write" else 1
        t0 = time.perf_counter()
        try:
            if step == "research":
                r = agents.research(prd)
                state["facts"], nxt, status = r.data, "write", "ok"
            elif step == "write":
                state["attempt"] += 1
                r = agents.write(prd, state["facts"], state["feedback"], state["attempt"])
                state["draft"], nxt, status = r.text, "fact_check", "ok"
            elif step == "fact_check":
                r = agents.fact_check(prd, state["facts"], state["draft"])
                if not r.data:
                    nxt, status = "polish", "pass"
                elif state["attempt"] < cfg["max_write_attempts"]:
                    # Rollback: discard the draft, keep the research, send the issues back to the writer.
                    state["feedback"], state["draft"], nxt, status = r.data, None, "write", "fail"
                    retries += 1
                else:
                    nxt, status = "needs_review", "fail"
            elif step == "polish":
                r = agents.polish(state["draft"])
                state["final"], nxt, status = r.text, "score", "ok"
            elif step == "score":
                sources = prd + json.dumps(state["facts"])
                state["rubric"] = score_post(state["final"], sources, cfg["rubric"])
                r = agents.judge(prd, state["final"])
                if r is not None:
                    state["rubric"]["llm_judge"] = r.data
                nxt, status = "done", "ok"
        except Exception as e:
            log(
                {
                    "seq": seq,
                    "agent": step,
                    "attempt": attempt,
                    "status": "error",
                    "output": f"{type(e).__name__}: {e}",
                    "model": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                    "latency_ms": (time.perf_counter() - t0) * 1000,
                    "detail": {},
                }
            )
            return {"status": "error", "error": str(e), **state, "retries": retries}

        log(
            {
                "seq": seq,
                "agent": step,
                "attempt": attempt,
                "status": status,
                "model": r.model if r else None,
                "input_tokens": r.input_tokens if r else 0,
                "output_tokens": r.output_tokens if r else 0,
                "cost_usd": r.cost_usd if r else 0.0,
                "latency_ms": (time.perf_counter() - t0) * 1000,
                "output": json.dumps(state["rubric"]) if step == "score" else (r.text if r else ""),
                "detail": {"issues": r.data, **r.detail} if step == "fact_check" else (r.detail if r else {}),
            }
        )
        step = nxt

    return {
        "status": "published" if step == "done" else "needs_review",
        **state,
        "retries": retries,
        "latency_ms": (time.perf_counter() - t_run) * 1000,
    }
