import os

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

SCHEMA = """
create table if not exists pipeline_runs (
    id bigserial primary key,
    prd_name text not null,
    prd text not null,
    mode text not null,
    status text not null default 'running' check (status in ('running', 'published', 'needs_review', 'error')),
    final_post text,
    rubric jsonb,
    retries int not null default 0,
    error text,
    started_at timestamptz not null default now(),
    finished_at timestamptz
);
create table if not exists steps (
    id bigserial primary key,
    run_id bigint not null references pipeline_runs(id) on delete cascade,
    seq int not null,
    agent text not null,
    attempt int not null,
    status text not null,
    model text,
    input_tokens int not null,
    output_tokens int not null,
    cost_usd numeric(12, 6) not null,
    latency_ms real not null,
    output text,
    detail jsonb,
    logged_at timestamptz not null default now(),
    unique (run_id, seq)
);
"""


def connect(dsn: str | None = None):
    conn = psycopg.connect(dsn or os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row)
    with conn.transaction():
        conn.execute("select pg_advisory_xact_lock(4444)")
        conn.execute(SCHEMA)
    return conn


def start_run(conn, prd_name: str, prd: str, mode: str) -> int:
    return conn.execute(
        "insert into pipeline_runs (prd_name, prd, mode) values (%s, %s, %s) returning id", (prd_name, prd, mode)
    ).fetchone()["id"]


def step_logger(conn, run_id: int):
    def log(s: dict):
        conn.execute(
            "insert into steps (run_id, seq, agent, attempt, status, model, input_tokens, output_tokens, cost_usd,"
            " latency_ms, output, detail) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (run_id, s["seq"], s["agent"], s["attempt"], s["status"], s["model"], s["input_tokens"],
             s["output_tokens"], s["cost_usd"], s["latency_ms"], s["output"], Jsonb(s["detail"])),
        )  # fmt: skip

    return log


def finish_run(conn, run_id: int, result: dict):
    conn.execute(
        "update pipeline_runs set status = %s, final_post = %s, rubric = %s, retries = %s, error = %s,"
        " finished_at = now() where id = %s",
        (result["status"], result.get("final"), Jsonb(result.get("rubric")), result["retries"], result.get("error"),
         run_id),
    )  # fmt: skip
