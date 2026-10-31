import json

from fastbreak import metrics, traces
from fastbreak.agent import evaluate
from fastbreak.agent.agent import ask
from fastbreak.db import connect
from tests.test_agent import TEAMS, FakeLLM, question, sql_reply


def test_a_question_is_traced_step_by_step(db_path, tmp_path):
    llm = FakeLLM(sql_reply("SELECT nope FROM teams"), sql_reply(TEAMS), "GSW and LAL.")
    result = ask("Which teams?", llm, db_path)
    trace_db = traces.connect(tmp_path / "traces.db")
    trace_id = traces.record(trace_db, result, llm.name, "ask")

    steps = trace_db.execute(
        "SELECT step, error IS NOT NULL FROM spans WHERE trace_id = ? ORDER BY seq", (trace_id,)
    ).fetchall()
    assert steps == [
        ("sql", 0),
        ("query", 1),  # the first query failed, and its error is kept
        ("sql", 0),
        ("query", 0),
        ("answer", 0),
        ("grounding", 0),
    ]
    row = trace_db.execute(
        "SELECT source, row_count, query_ran, answered, correct, output_tokens FROM traces"
    ).fetchone()
    assert row == ("ask", 2, 1, 1, None, 15)  # FakeLLM's replies are 5 tokens each


def test_an_eval_traces_each_question_with_its_score(db_path, tmp_path):
    conn = connect(db_path)
    trace_db = traces.connect(tmp_path / "traces.db")
    live = question(id="live", frozen=False)
    llm = FakeLLM(sql_reply(TEAMS), "GSW and LAL.")
    summary = evaluate.run(
        conn, llm, db_path, [live], tmp_path / "results", log=lambda *_: None, trace_db=trace_db
    )
    row = trace_db.execute("SELECT source, eval_run, question_id, correct FROM traces").fetchone()
    stem = summary["saved"].rsplit("/", 1)[-1].removesuffix(".jsonl")
    assert row == ("eval", stem, "live", 1)
    assert summary["output_tokens_per_correct"] == 10


def test_latency_is_per_model_and_step(db_path, tmp_path):
    trace_db = traces.connect(tmp_path / "traces.db")
    for _ in range(3):
        llm = FakeLLM(sql_reply(TEAMS), "GSW and LAL.")
        traces.record(trace_db, ask("Which teams?", llm, db_path), llm.name, "ask")
    rows = {(model, step): (n, p50) for model, step, n, p50, _ in metrics.latency(trace_db)}
    assert [step for _, step in rows] == ["sql", "query", "answer", "grounding", "total"]
    assert rows["fake", "sql"] == (3, 0.25)  # FakeLLM's replies take 0.25 s
    assert metrics.latency(trace_db, source="eval") == []


def test_cost_counts_runs_without_the_new_summary_fields(tmp_path):
    old = [
        {"id": "a", "correct": True, "seconds": 4.0, "output_tokens": 100},
        {"id": "b", "correct": False, "seconds": 6.0, "output_tokens": 300},
        {"summary": True, "model": "qwen3:14b", "questions": 2, "correct": 1},
    ]
    stopped = [{"id": "a", "correct": True, "seconds": 2.0, "output_tokens": 50}]
    (tmp_path / "1-old.jsonl").write_text("\n".join(json.dumps(r) for r in old) + "\n")
    (tmp_path / "2-stopped.jsonl").write_text(json.dumps(stopped[0]) + "\n")
    first, second = metrics.cost(tmp_path)
    assert (first["seconds_per_correct"], first["output_tokens_per_correct"]) == (10.0, 400)
    assert first["finished"] and not second["finished"]


def test_pipeline_failures_say_why(db_path):
    conn = connect(db_path)
    conn.executemany(
        "INSERT INTO ingest_runs (kind, started_at, finished_at, status, error)"
        " VALUES ('boxscores', strftime('%Y-%m-%dT%H:%M:%S', 'now'), NULL, ?, ?)",
        [
            ("ok", None),
            ("failed", "stopped after 2 failed calls in a row: probably blocked"),
            ("failed", "stopped after 10 failed calls in a row: probably blocked"),
        ],
    )
    conn.execute(
        "INSERT INTO ingest_runs (kind, started_at, status) VALUES ('nightly', '2020-01-01', 'ok')"
    )
    _, runs, reasons = metrics.pipeline(conn)
    assert runs == [("boxscores", 3, 1, 2, 0)]  # the 2020 run is older than 30 days
    assert reasons == [("boxscores", "probably blocked", 2)]
