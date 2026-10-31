"""Traces: what each question did, step by step, kept in data/traces.db.

One row in `traces` per question, asked with `fastbreak ask` or scored by an eval, and one
row in `spans` per step: each model call ('sql', 'answer'), each query run ('query') and the
grounding check ('grounding'). It's a separate file from nba.db, which the agent opens
read-only and the pipeline locks while it writes, so a trace never waits on a nightly run.
"""

import sqlite3
from datetime import UTC, datetime

TRACES_PATH = "data/traces.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at     TEXT NOT NULL,
    source         TEXT NOT NULL CHECK (source IN ('ask', 'eval')),
    eval_run       TEXT,                 -- the eval's results file, e.g. '2026-10-28T024005Z-qwen3-14b-think'
    question_id    TEXT,                 -- the test question, for an eval
    question       TEXT NOT NULL,
    model          TEXT NOT NULL,        -- e.g. 'qwen3:14b (thinking)'
    sql            TEXT,
    row_count      INTEGER,
    query_ran      INTEGER NOT NULL,
    answered       INTEGER NOT NULL,     -- the answer went out: grounded and not cut off
    correct        INTEGER,              -- for an eval; NULL for `fastbreak ask`
    error          TEXT,
    seconds        REAL NOT NULL,
    prompt_tokens  INTEGER NOT NULL,
    output_tokens  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS spans (
    trace_id       INTEGER NOT NULL REFERENCES traces (trace_id),
    seq            INTEGER NOT NULL,     -- the step's place in the trace, from 1
    step           TEXT NOT NULL,        -- 'sql', 'query', 'answer', 'grounding'
    seconds        REAL NOT NULL,
    prompt_tokens  INTEGER,              -- model steps only
    output_tokens  INTEGER,
    thinking_chars INTEGER,
    cut_off        INTEGER,
    error          TEXT,                 -- a query's error
    PRIMARY KEY (trace_id, seq)
);

CREATE INDEX IF NOT EXISTS traces_eval_run ON traces (eval_run);
"""


def connect(path=TRACES_PATH):
    """Open the traces database, creating its tables if they aren't there."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    return conn


def record(conn, result, model, source, eval_run=None, question_id=None, correct=None):
    """Save one agent `Result` as a trace with its spans. Returns the trace's id."""
    calls = result.calls
    cur = conn.execute(
        "INSERT INTO traces (started_at, source, eval_run, question_id, question, model, sql,"
        " row_count, query_ran, answered, correct, error, seconds, prompt_tokens, output_tokens)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now(UTC).isoformat(timespec="seconds"),
            source,
            eval_run,
            question_id,
            result.question,
            model,
            result.sql or None,
            len(result.rows) if result.query_ran else None,
            result.query_ran,
            result.answer is not None,
            correct,
            result.error,
            round(result.seconds, 3),
            sum(c["prompt_tokens"] for c in calls),
            sum(c["output_tokens"] for c in calls),
        ),
    )
    trace_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO spans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                trace_id,
                seq,
                s["step"],
                s["seconds"],
                s.get("prompt_tokens"),
                s.get("output_tokens"),
                s.get("thinking_chars"),
                s.get("cut_off"),
                s.get("error"),
            )
            for seq, s in enumerate(result.steps, 1)
        ],
    )
    conn.commit()
    return trace_id
