from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import db
from .llm import load_config
from .run import execute

STATIC = Path(__file__).parent / "static"


class NewRun(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    prd: str = Field(min_length=50, max_length=50_000)


def create_app(dsn: str | None = None) -> FastAPI:
    app = FastAPI(title="Multi-Agent Content Ops", version="1.0.0")
    conn, cfg = db.connect(dsn), load_config()

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(STATIC / "index.html")

    @app.post("/api/runs", status_code=202)
    def new_run(req: NewRun, background: BackgroundTasks):
        # Own connection per pipeline: psycopg connections aren't safe to share across threads mid-transaction.
        background.add_task(execute, req.name, req.prd, cfg, db.connect(dsn))
        return {"status": "started"}

    @app.get("/api/runs")
    def runs():
        return conn.execute(
            "select r.id, r.prd_name, r.mode, r.status, r.retries, r.rubric->>'score' as rubric_score,"
            " r.started_at, r.finished_at, coalesce(sum(s.input_tokens + s.output_tokens), 0) as tokens,"
            " coalesce(sum(s.cost_usd), 0)::float as cost_usd, coalesce(sum(s.latency_ms), 0) as latency_ms,"
            " count(s.id) as steps"
            " from pipeline_runs r left join steps s on s.run_id = r.id group by r.id order by r.id desc limit 100"
        ).fetchall()

    @app.get("/api/runs/{run_id}")
    def run(run_id: int):
        r = conn.execute("select * from pipeline_runs where id = %s", (run_id,)).fetchone()
        if not r:
            raise HTTPException(404, "run not found")
        r["steps"] = conn.execute(
            "select seq, agent, attempt, status, model, input_tokens, output_tokens, cost_usd::float as cost_usd,"
            " latency_ms, output, detail from steps where run_id = %s order by seq",
            (run_id,),
        ).fetchall()
        return r

    return app
