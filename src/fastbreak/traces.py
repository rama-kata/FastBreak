"""Traces: what each question did, step by step, kept in data/traces.db.

One row in `traces` per question, asked with `fastbreak ask` or scored by an eval, and one
row in `spans` per step: each model call ('sql', 'answer'), each query run ('query') and the
grounding check ('grounding'), plus the routing call ('route') when the question was routed.
Hard questions asked with `fastbreak ask` also go into `reviews`, for a person to check
after the answer has gone out (`fastbreak review`). It's a separate file from nba.db, which the agent opens
read-only and the pipeline locks while it writes, so a trace never waits on a nightly run.
"""

import json
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
    output_tokens  INTEGER NOT NULL,
    route          TEXT,                 -- 'simple' or 'hard' when routed
    columns        TEXT,                 -- the query's columns, as JSON
    rows           TEXT,                 -- its first 20 rows, as JSON
    answer         TEXT                  -- what the model wrote, sent or not (see `answered`)
);

CREATE TABLE IF NOT EXISTS spans (
    trace_id       INTEGER NOT NULL REFERENCES traces (trace_id),
    seq            INTEGER NOT NULL,     -- the step's place in the trace, from 1
    step           TEXT NOT NULL,        -- 'route', 'sql', 'query', 'answer', 'grounding'
    seconds        REAL NOT NULL,
    prompt_tokens  INTEGER,              -- model steps only
    output_tokens  INTEGER,
    thinking_chars INTEGER,
    cut_off        INTEGER,
    error          TEXT,                 -- a query's error
    PRIMARY KEY (trace_id, seq)
);

CREATE TABLE IF NOT EXISTS reviews (
    trace_id       INTEGER PRIMARY KEY REFERENCES traces (trace_id),
    status         TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'right', 'wrong')),
    note           TEXT,
    queued_at      TEXT NOT NULL,
    reviewed_at    TEXT
);

CREATE INDEX IF NOT EXISTS traces_eval_run ON traces (eval_run);
"""

# Columns added after traces.db first existed, so an older file gets them on connect.
ADDED_COLUMNS = {"route": "TEXT", "columns": "TEXT", "rows": "TEXT", "answer": "TEXT"}
REVIEW_ROWS = 20


def connect(path=TRACES_PATH):
    """Open the traces database, creating its tables if they aren't there."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    have = {row[1] for row in conn.execute("PRAGMA table_info(traces)")}
    for name, kind in ADDED_COLUMNS.items():
        if name not in have:
            conn.execute(f"ALTER TABLE traces ADD COLUMN {name} {kind}")
    return conn


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def record(conn, result, model, source, eval_run=None, question_id=None, correct=None):
    """Save one agent `Result` as a trace with its spans. Returns the trace's id."""
    calls = result.calls
    cur = conn.execute(
        "INSERT INTO traces (started_at, source, eval_run, question_id, question, model, sql,"
        " row_count, query_ran, answered, correct, error, seconds, prompt_tokens, output_tokens,"
        " route, columns, rows, answer)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            now(),
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
            result.route,
            json.dumps(result.columns) if result.query_ran else None,
            json.dumps([list(r) for r in result.rows[:REVIEW_ROWS]], default=str)
            if result.query_ran
            else None,
            result.draft_answer or None,
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


def queue_for_review(conn, trace_id):
    conn.execute(
        "INSERT OR IGNORE INTO reviews (trace_id, queued_at) VALUES (?, ?)", (trace_id, now())
    )
    conn.commit()


def pending_reviews(conn):
    """(trace_id, started_at, question, answer) for every answer still waiting, oldest first."""
    return conn.execute(
        "SELECT t.trace_id, t.started_at, t.question, t.answer FROM reviews r"
        " JOIN traces t USING (trace_id) WHERE r.status = 'pending' ORDER BY t.trace_id"
    ).fetchall()


def review_details(conn, trace_id):
    """Everything a reviewer needs for one trace, as a dict, or None if it doesn't exist."""
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT t.*, r.status AS review, r.note FROM traces t"
            " LEFT JOIN reviews r USING (trace_id) WHERE t.trace_id = ?",
            (trace_id,),
        ).fetchone()
    finally:
        conn.row_factory = None
    if row is None:
        return None
    details = dict(row)
    details["columns"] = json.loads(details["columns"] or "[]")
    details["rows"] = json.loads(details["rows"] or "[]")
    return details


def mark_review(conn, trace_id, verdict, note=None):
    """Record a person's verdict, 'right' or 'wrong'. Any trace can be marked, queued or not."""
    conn.execute(
        "INSERT INTO reviews (trace_id, status, note, queued_at, reviewed_at)"
        " VALUES (?, ?, ?, ?, ?) ON CONFLICT (trace_id) DO UPDATE SET"
        " status = excluded.status, note = excluded.note, reviewed_at = excluded.reviewed_at",
        (trace_id, verdict, note, now(), now()),
    )
    conn.commit()
