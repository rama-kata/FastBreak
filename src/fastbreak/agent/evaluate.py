"""Score the agent on the approved test questions.

A question is correct when the agent's query returns the same rows as the question's SQL
(`evals.same_answer`). Frozen questions compare against their saved answer; questions about
the current season run their SQL now. Each run is saved as one JSON line per question in
evals/results/, with the summary as the last line, so runs can be compared later. A run that
stops part-way still gets its summary, with `finished` false.
"""

import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from fastbreak import evals, traces
from fastbreak.agent.agent import ask

RESULTS = Path("evals/results")


class MissingAnswers(Exception):
    """Approved frozen questions with no saved answer, so they can't be scored."""

    def __init__(self, ids):
        super().__init__(", ".join(ids))
        self.ids = ids


def expected_rows(conn, question, answers=evals.ANSWERS):
    if question.frozen:
        return evals.frozen_answer(question, answers)
    return evals.run_sql(conn, question.sql)


def wilson(correct, total, z=1.96):
    """95% range for the true accuracy, given `correct` out of `total`."""
    if total == 0:
        return 0.0, 0.0
    p = correct / total
    d = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / d
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / d
    return centre - half, centre + half


def percentile(values, p):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(p / 100 * len(ordered)) - 1)]


def score_one(
    conn, question, llm, db_path, today=None, answers=evals.ANSWERS, trace_db=None, eval_run=None
):
    result = ask(question.question, llm, db_path, today)
    expected = expected_rows(conn, question, answers)
    # Scored on the query's rows: an answer that was cut off doesn't make a right query wrong.
    correct = result.query_ran and evals.same_answer(
        expected, result.rows, ordered=question.ordered, tolerance=question.tolerance
    )
    if trace_db is not None:
        traces.record(trace_db, result, llm.name, "eval", eval_run, question.id, correct)
    return {
        "id": question.id,
        "category": question.category,
        "difficulty": question.difficulty,
        "correct": correct,
        "error": result.error,
        "query_ran": result.query_ran,
        "route": result.route,
        "sql_attempts": result.sql_attempts,
        "cut_off": any(c["cut_off"] for c in result.calls),
        "grounded": result.answer is not None,
        "ungrounded": result.ungrounded,
        "seconds": round(result.seconds, 3),
        "prompt_tokens": sum(c["prompt_tokens"] for c in result.calls),
        "output_tokens": sum(c["output_tokens"] for c in result.calls),
        "question": question.question,
        "sql": result.sql,
        "rows": [list(r) for r in result.rows[:20]],
        "expected": [list(r) for r in expected],
        "answer": result.draft_answer,
    }


def summarize(records, model, finished=True):
    total = len(records)
    correct = sum(r["correct"] for r in records)
    low, high = wilson(correct, total)
    answered = [r for r in records if r["query_ran"]]
    by = defaultdict(lambda: [0, 0])
    for r in records:
        for key in (r["category"], r["difficulty"]):
            by[key][0] += r["correct"]
            by[key][1] += 1
    seconds = [r["seconds"] for r in records]
    output_tokens = sum(r["output_tokens"] for r in records)
    routed = [r for r in records if r.get("route")]
    return {
        "summary": True,
        "model": model,
        "finished": finished,
        "questions": total,
        "correct": correct,
        "accuracy": round(correct / total, 3) if total else 0.0,
        "accuracy_95": [round(low, 3), round(high, 3)],
        "query_failed": total - len(answered),
        "cut_off": sum(r["cut_off"] for r in records),
        "grounded": sum(r["grounded"] for r in answered),
        "grounded_and_wrong": sum(r["grounded"] and not r["correct"] for r in answered),
        "by": {k: f"{c}/{n}" for k, (c, n) in sorted(by.items())},
        "p50_seconds": percentile(seconds, 50),
        "p95_seconds": percentile(seconds, 95),
        "prompt_tokens": sum(r["prompt_tokens"] for r in records),
        "output_tokens": output_tokens,
        # The models run locally, so cost is model time and tokens, over the right answers.
        "seconds": round(sum(seconds), 1),
        "seconds_per_correct": round(sum(seconds) / correct, 1) if correct else None,
        "output_tokens_per_correct": round(output_tokens / correct) if correct else None,
    } | ({"routing": routing(routed)} if routed else {})


def routing(records):
    """How the router's choices compare with the test set's simple/hard labels."""
    pairs = defaultdict(lambda: [0, 0])  # (label, route) -> [questions, correct]
    for r in records:
        pairs[r["difficulty"], r["route"]][0] += 1
        pairs[r["difficulty"], r["route"]][1] += r["correct"]
    agree = sum(n for (label, route), (n, _) in pairs.items() if label == route)
    return {
        "agrees": f"{agree}/{len(records)}",
        # The costly mistake: a hard question sent to thinking off.
        "hard_sent_fast": pairs["hard", "simple"][0],
        "simple_sent_thinking": pairs["simple", "hard"][0],
        "by": {
            f"{label}->{route}": f"{c}/{n} right"
            for (label, route), (n, c) in sorted(pairs.items())
        },
    }


def run(
    conn,
    llm,
    db_path,
    questions,
    out_dir=RESULTS,
    today=None,
    answers=evals.ANSWERS,
    log=print,
    trace_db=None,
):
    """Score `questions` (approved only) and save the run. Returns the summary.

    With `trace_db`, each question is also saved as a trace, tagged with the run's file name.
    """
    questions = [q for q in questions if q.status == "approved"]
    missing = [q.id for q in questions if q.frozen and evals.frozen_answer(q, answers) is None]
    if missing:
        raise MissingAnswers(missing)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    slug = llm.name.replace(" (thinking)", "-think").replace(" (routed)", "-routed")
    slug = slug.replace(":", "-").replace("/", "-")
    path = out_dir / f"{stamp}-{slug}.jsonl"
    records = []
    with path.open("w") as fh:
        try:
            for i, q in enumerate(questions, 1):
                record = score_one(conn, q, llm, db_path, today, answers, trace_db, path.stem)
                records.append(record)
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                mark = "ok   " if record["correct"] else "WRONG" if record["query_ran"] else "ERROR"
                log(f"[{i:>2}/{len(questions)}] {mark} {q.id}  ({record['seconds']:.1f}s)")
        except BaseException:  # the model failed, or Ctrl-C: save what was scored, then stop
            fh.write(json.dumps(summarize(records, llm.name, finished=False)) + "\n")
            log(f"stopped after {len(records)} of {len(questions)} questions; saved to {path}")
            raise
        summary = summarize(records, llm.name)
        fh.write(json.dumps(summary) + "\n")
    summary["saved"] = str(path)
    return summary
