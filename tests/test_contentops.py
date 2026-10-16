import os
from pathlib import Path

import pytest

os.environ["MOCK_MODE"] = "1"

from contentops.agents import MockAgents  # noqa: E402
from contentops.checks import reading_ease, score_post, unsupported_numbers  # noqa: E402
from contentops.llm import load_config, parse_json  # noqa: E402
from contentops.orchestrator import run_pipeline  # noqa: E402

PRDS = Path(__file__).resolve().parent.parent / "examples" / "prds"
CFG = load_config()
PRD = (PRDS / "smart-inbox.md").read_text(encoding="utf-8")


def test_unsupported_numbers():
    src = "Accuracy was 91%. 2,400 users. Launch March 3."
    assert unsupported_numbers("We hit 91% with 2400 users on March 3 [F2].", src) == []
    issues = unsupported_numbers("We hit 91%. Productivity rose 37%.", src)
    assert len(issues) == 1 and "37" in issues[0]["problem"]


def test_rubric_checks():
    post = "# Title\n\n**TL;DR:** It is good.\n\n## A\n\nShort words here.\n\n## B\n\nMore.\n\n## C\n\nDone [F1]."
    r = score_post(post, "", {"min_words": 1, "max_words": 100, "min_sections": 3, "min_reading_ease": 0})
    assert r["checks"]["has_title"] and r["checks"]["has_tldr"] and r["checks"]["enough_sections"]
    assert r["checks"]["no_citation_markers"] is False
    assert reading_ease("The cat sat on the mat.") > reading_ease(
        "Organizational interdependencies necessitate comprehensive reconsideration."
    )


def test_parse_json_accepts_fenced_blocks():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json("[1, 2]") == [1, 2]


def _run(hallucinations, max_attempts=3):
    steps = []
    cfg = {**CFG, "max_write_attempts": max_attempts}
    result = run_pipeline(PRD, MockAgents(CFG, {"Smart Inbox Triage": hallucinations}), cfg, steps.append)
    return result, steps


def test_clean_run_publishes_without_retries():
    result, steps = _run(0)
    assert result["status"] == "published" and result["retries"] == 0
    assert [s["agent"] for s in steps] == ["research", "write", "fact_check", "polish", "score"]
    assert result["rubric"]["checks"]["numbers_supported"] and "[F" not in result["final"]


def test_failed_fact_check_rolls_back_and_rewrites():
    result, steps = _run(2)
    assert [s["agent"] for s in steps] == [
        "research", "write", "fact_check", "write", "fact_check", "write", "fact_check", "polish", "score",
    ]  # fmt: skip
    assert [s["status"] for s in steps if s["agent"] == "fact_check"] == ["fail", "fail", "pass"]
    assert [s["attempt"] for s in steps if s["agent"] == "write"] == [1, 2, 3]
    assert result["retries"] == 2 and MockAgents.HALLUCINATION not in result["final"]


def test_exhausted_retries_escalate_to_human_review():
    result, steps = _run(5, max_attempts=2)
    assert result["status"] == "needs_review" and result["final"] is None
    assert steps[-1]["agent"] == "fact_check" and steps[-1]["status"] == "fail"


def test_agent_exception_is_logged_and_stops_run():
    class Boom(MockAgents):
        def polish(self, draft):
            raise RuntimeError("model refused")

    steps = []
    result = run_pipeline(PRD, Boom(CFG, {}), CFG, steps.append)
    assert result["status"] == "error" and steps[-1]["status"] == "error" and steps[-1]["agent"] == "polish"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="needs Postgres")
def test_steps_are_logged_to_postgres_and_served():
    from fastapi.testclient import TestClient

    from contentops import db
    from contentops.app import create_app
    from contentops.run import execute

    run = execute("pytest-prd", (PRDS / "usage-billing.md").read_text(encoding="utf-8"), CFG, db.connect())
    client = TestClient(create_app())
    r = client.get(f"/api/runs/{run['run_id']}").json()
    assert r["status"] == "published" and r["retries"] == 2
    assert [s["seq"] for s in r["steps"]] == list(range(1, 10))
    listed = next(x for x in client.get("/api/runs").json() if x["id"] == run["run_id"])
    assert listed["steps"] == 9 and listed["cost_usd"] > 0
    assert client.get("/api/runs/999999999").status_code == 404
    assert client.post("/api/runs", json={"name": "x", "prd": "too short"}).status_code == 422
