"""The test set: questions with the SQL that answers them, and how an answer is scored.

A predicted query is correct when it returns the same rows as the question's SQL.
Column names and column order don't matter, and extra columns are allowed (an agent
that also returns a player's ID or team is still right). Extra or missing rows are not.
Text is compared ignoring case and surrounding spaces.
"""

import json
import sqlite3
import tomllib
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path

QUESTIONS = Path("evals/questions.toml")
ANSWERS = Path("evals/answers")
CATEGORIES = {"lookup", "ranking", "count", "split", "team", "streak", "edge"}
DIFFICULTIES = {"simple", "hard"}  # simple goes to the small local model, hard to the big one
STATUSES = {"draft", "approved"}  # only approved questions count towards the score
DEFAULT_TOLERANCE = 0.05  # averages are compared to 1 decimal place, the way they're reported


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    sql: str
    category: str
    difficulty: str
    status: str = "draft"
    ordered: bool = False  # True when the order of the rows is part of the answer
    frozen: bool = True  # False for questions about the current season, whose answer moves
    tolerance: float = DEFAULT_TOLERANCE
    notes: str = ""


def load_questions(path=QUESTIONS):
    """Every question in the file, checked for unknown fields, bad values and repeated IDs."""
    raw = tomllib.loads(Path(path).read_text())["question"]
    questions, seen = [], set()
    for entry in raw:
        q = Question(**entry)  # an unknown field is a TypeError here, not silently ignored
        problems = [
            f"category {q.category!r}" * (q.category not in CATEGORIES),
            f"difficulty {q.difficulty!r}" * (q.difficulty not in DIFFICULTIES),
            f"status {q.status!r}" * (q.status not in STATUSES),
            "repeated id" * (q.id in seen),
        ]
        if any(problems):
            raise ValueError(f"{q.id}: bad {', '.join(p for p in problems if p)}")
        seen.add(q.id)
        questions.append(q)
    return questions


def run_sql(conn, sql):
    """Rows from a read-only query. Anything that would change the database is refused."""
    conn.execute("PRAGMA query_only = ON")
    try:
        return [tuple(row) for row in conn.execute(sql).fetchall()]
    finally:
        conn.execute("PRAGMA query_only = OFF")


def _sort_key(row):
    """Sort rows of mixed types the same way every time: numbers before text, None first.
    Text sorts ignoring case, the way it's compared."""
    return tuple(
        (v is not None, isinstance(v, str), v.casefold() if isinstance(v, str) else v or 0)
        for v in row
    )


def _close(a, b, tolerance):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tolerance  # 27 == 27.0, and averages within the tolerance
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().casefold() == b.strip().casefold()  # "Home" is "home"
    return a == b


def _same_rows(want, got, ordered, tolerance):
    if not ordered:
        want, got = sorted(want, key=_sort_key), sorted(got, key=_sort_key)
    return all(
        all(_close(a, b, tolerance) for a, b in zip(w, g, strict=True))
        for w, g in zip(want, got, strict=True)
    )


def same_answer(expected, predicted, ordered=False, tolerance=DEFAULT_TOLERANCE):
    """True when `predicted` has the same rows as `expected`, allowing extra columns.

    Each expected column is matched to a different predicted column, in any order. With
    `ordered`, the rows must also come back in the same order.
    """
    if len(expected) != len(predicted):
        return False
    if not expected:
        return True
    width, pred_width = len(expected[0]), len(predicted[0])
    for columns in permutations(range(pred_width), width):
        got = [tuple(row[c] for c in columns) for row in predicted]
        if _same_rows(expected, got, ordered, tolerance):
            return True
    return False


def answer_path(question, answers=ANSWERS):
    return Path(answers) / f"{question.id}.json"


def freeze(conn, question, answers=ANSWERS):
    """Save what the question's SQL returns now, as the answer a person checks and approves."""
    path = answer_path(question, answers)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = run_sql(conn, question.sql)
    lines = ",\n".join(f"  {json.dumps(list(row), ensure_ascii=False)}" for row in rows)
    path.write_text(f'{{"id": {json.dumps(question.id)}, "rows": [\n{lines}\n]}}\n')
    return rows


def frozen_answer(question, answers=ANSWERS):
    path = answer_path(question, answers)
    if not path.exists():
        return None
    return [tuple(row) for row in json.loads(path.read_text())["rows"]]


def check(conn, questions, answers=ANSWERS):
    """For each question: does its SQL run, and does it still return the frozen answer?

    Returns (question, problem) pairs; problem is None when everything is fine.
    """
    results = []
    for q in questions:
        try:
            rows = run_sql(conn, q.sql)
        except sqlite3.Error as e:
            results.append((q, f"SQL error: {e}"))
            continue
        if not rows:
            results.append((q, "returns no rows"))
            continue
        if not q.frozen:
            results.append((q, None))
            continue
        saved = frozen_answer(q, answers)
        if saved is None:
            results.append((q, "no frozen answer yet (run: fastbreak questions freeze)"))
        elif not same_answer(saved, rows, ordered=q.ordered, tolerance=q.tolerance):
            results.append((q, "SQL no longer returns the frozen answer"))
        else:
            results.append((q, None))
    return results
