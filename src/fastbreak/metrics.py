"""The numbers the README promises: latency per step, cost per correct answer, and the
pipeline's failure rate per step.

Latency comes from the traces, cost from the saved eval runs in evals/results/ (so runs from
before traces existed count too), and failure rates from the pipeline's own tables in nba.db.
"""

import json
from collections import defaultdict
from pathlib import Path

from fastbreak.agent.evaluate import RESULTS, percentile


def latency(trace_db, source=None):
    """p50 and p95 seconds per model and step, plus 'total' for a whole question.

    Returns (model, step, count, p50, p95) rows, `source` limiting it to 'ask' or 'eval'.
    """
    where, params = ("WHERE t.source = ?", (source,)) if source else ("", ())
    seconds = defaultdict(list)
    for model, step, s in trace_db.execute(
        f"SELECT t.model, s.step, s.seconds FROM spans s JOIN traces t USING (trace_id) {where}",
        params,
    ):
        seconds[model, step].append(s)
    for model, s in trace_db.execute(f"SELECT t.model, t.seconds FROM traces t {where}", params):
        seconds[model, "total"].append(s)
    order = {"sql": 0, "query": 1, "answer": 2, "grounding": 3, "total": 4}
    return [
        (model, step, len(v), percentile(v, 50), percentile(v, 95))
        for (model, step), v in sorted(seconds.items(), key=lambda kv: (kv[0][0], order[kv[0][1]]))
    ]


def cost(results_dir=RESULTS):
    """Model time and output tokens per correct answer, for each saved eval run, oldest first.

    Worked out from the per-question lines, not the summary, which older runs don't have
    these fields in. A run that stopped part-way is marked unfinished.
    """
    runs = []
    for path in sorted(Path(results_dir).glob("*.jsonl")):
        lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        records = [r for r in lines if not r.get("summary")]
        summary = next((r for r in lines if r.get("summary")), {})
        correct = sum(r["correct"] for r in records)
        seconds = sum(r["seconds"] for r in records)
        tokens = sum(r["output_tokens"] for r in records)
        runs.append(
            {
                "run": path.stem,
                "model": summary.get("model", "?"),
                "finished": bool(summary) and summary.get("finished", True),
                "questions": len(records),
                "correct": correct,
                "seconds": seconds,
                "seconds_per_correct": seconds / correct if correct else None,
                "output_tokens_per_correct": tokens / correct if correct else None,
            }
        )
    return runs


def pipeline(conn, days=30):
    """Failure rates for the pipeline: per game step, and per run kind over the last `days`.

    Returns (steps, runs, reasons). steps: (step, games, failed, retried), where retried
    counts games that needed more than one attempt, failed or not. runs: (kind, runs, ok,
    failed, running). reasons: (kind, reason, runs) for the failed runs, the reason being the
    end of the run's error ("probably blocked", "stopped by Ctrl-C or kill").
    """
    steps = conn.execute(
        "SELECT step, COUNT(*), SUM(status = 'failed'), SUM(attempts > 1)"
        " FROM game_ingest GROUP BY step ORDER BY step"
    ).fetchall()
    runs = conn.execute(
        "SELECT kind, COUNT(*), SUM(status = 'ok'), SUM(status = 'failed'),"
        " SUM(status = 'running') FROM ingest_runs"
        " WHERE started_at >= strftime('%Y-%m-%dT%H:%M:%S', 'now', ?) GROUP BY kind ORDER BY kind",
        (f"-{days} days",),
    ).fetchall()
    reasons = conn.execute(
        "SELECT kind, substr(error, instr(error, ': ') + 2) AS reason, COUNT(*) FROM ingest_runs"
        " WHERE status = 'failed' AND started_at >= strftime('%Y-%m-%dT%H:%M:%S', 'now', ?)"
        " GROUP BY kind, reason ORDER BY kind, COUNT(*) DESC",
        (f"-{days} days",),
    ).fetchall()
    return steps, runs, reasons
