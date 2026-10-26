import json
from datetime import date
from pathlib import Path

import pytest

from fastbreak import evals
from fastbreak.agent import evaluate
from fastbreak.agent.agent import ask
from fastbreak.agent.grounding import numbers_in, ungrounded_numbers
from fastbreak.agent.llm import Reply
from fastbreak.agent.prompt import sql_system_prompt, stats_schema
from fastbreak.agent.sql import QueryError, extract_sql, run_readonly
from fastbreak.db import connect, init_db

TEAMS = "SELECT abbreviation FROM teams ORDER BY abbreviation"


class FakeLLM:
    """Replies with the next canned text, and remembers what it was sent."""

    name = "fake"

    def __init__(self, *texts):
        self.texts = list(texts)
        self.sent = []

    def chat(self, messages):
        self.sent.append(messages)
        text = self.texts.pop(0)
        cut_off = text.startswith("CUT:")
        return Reply(text.removeprefix("CUT:"), "", 10, 5, 0.25, cut_off)


def sql_reply(sql):
    return f"```sql\n{sql}\n```"


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    conn = connect(path)
    init_db(conn)
    conn.execute("INSERT INTO teams VALUES (1610612744, 'GSW', 'Golden State Warriors')")
    conn.execute("INSERT INTO teams VALUES (1610612747, 'LAL', 'Los Angeles Lakers')")
    conn.commit()
    conn.close()
    return path


# --- the query ------------------------------------------------------------------------


def test_sql_comes_from_the_last_sql_block_or_the_whole_reply():
    assert (
        extract_sql("First:\n```sql\nSELECT 1\n```\nBetter:\n```sql\nSELECT 2;\n```") == "SELECT 2"
    )
    assert extract_sql("SELECT 3;") == "SELECT 3"


def test_queries_run_read_only(db_path):
    for sql in ("DELETE FROM teams", "INSERT INTO teams VALUES (1, 'X', 'X')", "DROP TABLE teams"):
        with pytest.raises(QueryError):
            run_readonly(db_path, sql)
    assert run_readonly(db_path, "SELECT COUNT(*) FROM teams").rows == [(2,)]


def test_one_statement_at_a_time(db_path):
    with pytest.raises(QueryError):
        run_readonly(db_path, "SELECT 1; DELETE FROM teams")


def test_a_runaway_query_is_stopped(db_path):
    endless = (
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT COUNT(*) FROM c"
    )
    with pytest.raises(QueryError, match="longer than"):
        run_readonly(db_path, endless, timeout=0.5)


def test_rows_are_capped(db_path):
    result = run_readonly(db_path, TEAMS, max_rows=1)
    assert result.rows == [("GSW",)] and result.truncated


# --- grounding ------------------------------------------------------------------------


def test_numbers_are_read_the_way_people_write_them():
    found = [v for v, _ in numbers_in("3,057 threes from 2015-16, +57, -12, 27.5, a 24-0 start")]
    assert found == [3057, 2015, 16, 57, -12, 27.5, 24, 0]


def test_a_rounded_number_is_grounded_but_a_wrong_one_is_not():
    assert ungrounded_numbers("He averaged 30.1.", [(30.06,)]) == []
    assert ungrounded_numbers("He averaged 30.2.", [(30.06,)]) == [30.2]


def test_numbers_from_dates_percentages_and_the_question_are_grounded():
    assert ungrounded_numbers("60 on December 5, 2016.", [(60, "2016-12-05")]) == []
    assert ungrounded_numbers("He shot 45.4%.", [(0.454,)]) == []
    assert ungrounded_numbers("In 2015-16 he had 79.", [(79,)], "How many in 2015-16?") == []


def test_an_invented_number_is_caught():
    assert ungrounded_numbers("73 points and 10 rebounds.", [(73,)]) == [10]


# --- the agent ------------------------------------------------------------------------


def test_the_prompt_has_the_stats_tables_and_this_season():
    prompt = sql_system_prompt(date(2026, 10, 25))
    assert "CREATE TABLE IF NOT EXISTS player_game_stats" in prompt
    assert "ingest_runs" not in stats_schema()  # pipeline bookkeeping stays out
    assert "this season is '2026-27' and last season is '2025-26'" in prompt


def test_a_grounded_answer_goes_out(db_path):
    llm = FakeLLM(sql_reply("SELECT COUNT(*) FROM teams"), "There are 2 teams.")
    result = ask("How many teams?", llm, db_path)
    assert (result.rows, result.answer, result.error) == ([(2,)], "There are 2 teams.", None)
    assert [c["step"] for c in result.calls] == ["sql", "answer"]


def test_an_answer_with_an_invented_number_is_held_back(db_path):
    llm = FakeLLM(sql_reply("SELECT COUNT(*) FROM teams"), "There are 30 teams.")
    result = ask("How many teams?", llm, db_path)
    assert result.answer is None
    assert (result.draft_answer, result.ungrounded) == ("There are 30 teams.", [30])


def test_a_failed_query_gets_one_retry_that_sees_the_error(db_path):
    llm = FakeLLM(sql_reply("SELECT nope FROM teams"), sql_reply(TEAMS), "GSW and LAL.")
    result = ask("Which teams?", llm, db_path)
    assert (result.sql_attempts, result.error, result.rows) == (2, None, [("GSW",), ("LAL",)])
    assert "no such column: nope" in llm.sent[1][-1]["content"]


def test_two_failed_queries_give_no_answer(db_path):
    llm = FakeLLM(sql_reply("SELECT nope FROM teams"), sql_reply("SELECT nope FROM teams"))
    result = ask("Which teams?", llm, db_path)
    assert result.answer is None and result.error.startswith("query failed")
    assert len(llm.sent) == 2  # no answer call after the query failed


def test_a_cut_off_query_is_retried_not_run(db_path):
    llm = FakeLLM(
        "CUT:" + sql_reply("SELECT COUNT(*) FROM teams"), sql_reply(TEAMS), "GSW and LAL."
    )
    result = ask("Which teams?", llm, db_path)
    assert (result.sql_attempts, result.rows) == (2, [("GSW",), ("LAL",)])
    assert "cut off" in llm.sent[1][-1]["content"]
    assert [c["cut_off"] for c in result.calls] == [True, False, False]


def test_a_cut_off_answer_doesnt_go_out(db_path):
    llm = FakeLLM(sql_reply("SELECT COUNT(*) FROM teams"), "CUT:There are 2")
    result = ask("How many teams?", llm, db_path)
    assert result.answer is None and result.error.startswith("the answer was cut off")


# --- scoring --------------------------------------------------------------------------


def question(**fields):
    base = {"id": "q", "question": "Which teams?", "sql": TEAMS, "status": "approved"}
    return evals.Question(**{**base, "category": "team", "difficulty": "simple", **fields})


def test_the_score_compares_rows_and_skips_drafts(db_path, tmp_path):
    conn = connect(db_path)
    right, wrong, draft = (
        question(id="right"),
        question(id="wrong"),
        question(id="draft", status="draft"),
    )
    for q in (right, wrong, draft):
        evals.freeze(conn, q, tmp_path / "answers")
    llm = FakeLLM(
        sql_reply("SELECT abbreviation, name FROM teams"),  # extra column: still right
        "GSW and LAL.",
        sql_reply("SELECT abbreviation FROM teams WHERE abbreviation = 'GSW'"),  # a row short
        "GSW.",
    )
    summary = evaluate.run(
        conn,
        llm,
        db_path,
        [right, wrong, draft],
        tmp_path / "results",
        answers=tmp_path / "answers",
        log=lambda *_: None,
    )
    assert (summary["questions"], summary["correct"], summary["grounded_and_wrong"]) == (2, 1, 1)
    lines = [json.loads(line) for line in Path(summary["saved"]).read_text().splitlines()]
    assert [line.get("id") for line in lines[:2]] == ["right", "wrong"] and lines[-1]["summary"]


def test_a_live_question_is_scored_against_its_sql_now(db_path, tmp_path):
    conn = connect(db_path)
    live = question(id="live", frozen=False)
    llm = FakeLLM(sql_reply(TEAMS), "GSW and LAL.")
    summary = evaluate.run(conn, llm, db_path, [live], tmp_path, log=lambda *_: None)
    assert summary["correct"] == 1


def test_the_accuracy_range_is_wide_for_few_questions():
    low, high = evaluate.wilson(40, 50)
    assert (round(low, 2), round(high, 2)) == (0.67, 0.89)
