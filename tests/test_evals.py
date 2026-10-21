import pytest

from fastbreak import evals
from fastbreak.db import connect, init_db

TOP = [("Stephen Curry", 402), ("James Harden", 377)]


def test_same_rows_in_another_order_match():
    assert evals.same_answer(TOP, list(reversed(TOP)))


def test_order_counts_when_the_question_says_so():
    assert not evals.same_answer(TOP, list(reversed(TOP)), ordered=True)
    assert evals.same_answer(TOP, TOP, ordered=True)


def test_columns_can_come_back_in_any_order_with_extras():
    predicted = [(402, 201939, "Stephen Curry", "GSW"), (377, 201935, "James Harden", "HOU")]
    assert evals.same_answer(TOP, predicted)


def test_a_missing_or_extra_row_is_wrong():
    assert not evals.same_answer(TOP, TOP[:1])
    assert not evals.same_answer(TOP, [*TOP, ("Damian Lillard", 377)])


def test_a_missing_column_is_wrong():
    assert not evals.same_answer(TOP, [("Stephen Curry",), ("James Harden",)])


def test_a_wrong_value_is_wrong():
    assert not evals.same_answer(TOP, [("Stephen Curry", 402), ("James Harden", 376)])


def test_averages_match_to_one_decimal():
    assert evals.same_answer([("Luka Doncic", 33.9)], [("Luka Doncic", 33.8696)])
    assert not evals.same_answer([("Luka Doncic", 33.9)], [("Luka Doncic", 33.7)])


def test_whole_numbers_match_their_float_form():
    assert evals.same_answer([(27,)], [(27.0,)])


def test_no_rows_matches_no_rows():
    assert evals.same_answer([], [])


def test_one_predicted_column_cant_fill_two_expected_ones():
    assert not evals.same_answer([(5, 5)], [(5,)])


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    conn.execute("INSERT INTO teams VALUES (1610612744, 'GSW', 'Golden State Warriors')")
    conn.commit()
    yield conn
    conn.close()


def test_sql_that_changes_the_database_is_refused(db):
    with pytest.raises(Exception, match="readonly"):
        evals.run_sql(db, "DELETE FROM teams")
    assert evals.run_sql(db, "SELECT COUNT(*) FROM teams") == [(1,)]


def question(**fields):
    base = {"id": "q", "question": "?", "sql": "SELECT abbreviation FROM teams"}
    return evals.Question(**{**base, "category": "lookup", "difficulty": "simple", **fields})


def test_check_reports_each_kind_of_problem(db, tmp_path):
    moved, empty = question(id="moved"), question(id="empty")
    evals.freeze(db, moved, tmp_path)
    evals.freeze(db, empty, tmp_path)
    db.execute("INSERT INTO teams VALUES (1610612747, 'LAL', 'Los Angeles Lakers')")
    db.commit()
    empty_now = question(id="empty", sql="SELECT abbreviation FROM teams WHERE team_id < 0")
    broken = question(id="broken", sql="SELECT nope FROM teams")
    unfrozen = question(id="unfrozen")
    live = question(id="live", frozen=False)
    problems = {
        q.id: p for q, p in evals.check(db, [moved, empty_now, broken, unfrozen, live], tmp_path)
    }
    assert problems["moved"] == "SQL no longer returns the frozen answer"  # LAL was added
    assert problems["empty"] == "returns no rows"
    assert problems["broken"].startswith("SQL error")
    assert problems["unfrozen"].startswith("no frozen answer yet")
    assert problems["live"] is None


def write_questions(tmp_path, body):
    path = tmp_path / "questions.toml"
    path.write_text(body)
    return path


ONE = """
[[question]]
id = "{id}"
question = "How many teams are there?"
sql = "SELECT COUNT(*) FROM teams"
category = "{category}"
difficulty = "simple"
"""


def test_questions_load_from_toml(tmp_path):
    [q] = evals.load_questions(write_questions(tmp_path, ONE.format(id="a", category="count")))
    assert (q.id, q.status, q.ordered, q.frozen) == ("a", "draft", False, True)


def test_a_bad_category_or_a_repeated_id_is_refused(tmp_path):
    with pytest.raises(ValueError, match="category"):
        evals.load_questions(write_questions(tmp_path, ONE.format(id="a", category="vibes")))
    twice = ONE.format(id="a", category="count") * 2
    with pytest.raises(ValueError, match="repeated id"):
        evals.load_questions(write_questions(tmp_path, twice))


def test_an_unknown_field_is_refused(tmp_path):
    typo = ONE.format(id="a", category="count") + "ordred = true\n"
    with pytest.raises(TypeError):
        evals.load_questions(write_questions(tmp_path, typo))


def test_the_real_test_set_loads_and_every_frozen_question_has_an_answer():
    questions = evals.load_questions()
    assert len(questions) >= 50
    missing = [q.id for q in questions if q.frozen and evals.frozen_answer(q) is None]
    assert missing == [], "run: uv run fastbreak questions freeze"
