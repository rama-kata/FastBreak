"""The `fastbreak` command: uv run fastbreak <load-seasons | boxscores | nightly | status | questions | ask | eval | metrics>."""

import argparse
import signal
import sys

from fastbreak import evals, metrics, traces
from fastbreak.agent import evaluate
from fastbreak.agent.agent import ask
from fastbreak.agent.llm import LLMError, Ollama
from fastbreak.db import connect, init_db
from fastbreak.pipeline import run
from fastbreak.pipeline.fetch import Fetcher

DB_PATH = "data/nba.db"
CACHE_DIR = "data/raw"
DEFAULT_MODEL = "qwen3:14b"


def stop_on_sigterm():
    """Make `kill <pid>` stop a run the same way Ctrl-C does, so it records that it was stopped."""

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)


def main():
    parser = argparse.ArgumentParser(prog="fastbreak", description="NBA stats pipeline")
    parser.add_argument("--db", default=DB_PATH, help=f"database file (default {DB_PATH})")
    parser.add_argument(
        "--traces",
        default=traces.TRACES_PATH,
        help=f"where questions are traced (default {traces.TRACES_PATH})",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    seasons = commands.add_parser("load-seasons", help="load game logs for every season")
    seasons.add_argument("--from", dest="first", default="2015-16", help="first season")

    boxscores = commands.add_parser("boxscores", help="fill in starters and exact minutes")
    boxscores.add_argument("--limit", type=int, help="stop after this many games")
    boxscores.add_argument(
        "--max-failures-in-row",
        type=int,
        default=run.MAX_FAILURES_IN_ROW,
        help=f"stop after this many failed games in a row (default {run.MAX_FAILURES_IN_ROW})",
    )

    nightly = commands.add_parser("nightly", help="new games and corrections for this season")
    nightly.add_argument(
        "--days",
        type=int,
        default=run.NIGHTLY_DAYS,
        help=f"re-check box scores from this many days back (default {run.NIGHTLY_DAYS})",
    )

    commands.add_parser("status", help="show pipeline progress")

    questions = commands.add_parser("questions", help="the test set in evals/questions.toml")
    actions = questions.add_subparsers(dest="action", required=True)
    actions.add_parser("check", help="run every question's SQL and compare to its saved answer")
    freeze = actions.add_parser("freeze", help="save answers for questions that don't have one")
    freeze.add_argument("--id", help="save this draft question's answer again, replacing it")
    show = actions.add_parser("show", help="one question, its SQL and its answer, for review")
    show.add_argument("id")

    for name, text in (("ask", "answer one question"), ("eval", "score the agent on the test set")):
        p = commands.add_parser(name, help=text)
        p.add_argument(
            "--model", default=DEFAULT_MODEL, help=f"Ollama model (default {DEFAULT_MODEL})"
        )
        p.add_argument("--think", action="store_true", help="turn the model's reasoning on")
        if name == "ask":
            p.add_argument("question")
        else:
            p.add_argument("--id", action="append", help="only this question (repeatable)")

    show_metrics = commands.add_parser(
        "metrics", help="latency per step, cost per correct answer, pipeline failures"
    )
    show_metrics.add_argument(
        "--source", choices=("ask", "eval"), help="latency for only these traces"
    )

    args = parser.parse_args()
    conn = connect(args.db)
    init_db(conn)
    fetcher = Fetcher(CACHE_DIR)
    stop_on_sigterm()

    try:
        if args.command == "load-seasons":
            run.ingest_seasons(conn, fetcher, first=args.first)
        elif args.command == "boxscores":
            run.ingest_boxscores(
                conn, fetcher, limit=args.limit, max_failures_in_row=args.max_failures_in_row
            )
        elif args.command == "nightly":
            run.ingest_nightly(conn, fetcher, days=args.days)
        elif args.command == "questions":
            questions_command(conn, args)
        elif args.command == "ask":
            ask_command(args)
        elif args.command == "eval":
            eval_command(conn, args)
        elif args.command == "metrics":
            metrics_command(conn, args)
        else:
            print_status(conn)
    except run.RunInProgress as e:
        sys.exit(f"{e}. Stop it first, or wait for it to finish (uv run fastbreak status).")
    except KeyboardInterrupt:
        if args.command == "ask":
            sys.exit("stopped.")
        if args.command == "eval":
            sys.exit(
                "stopped. An eval doesn't resume: running it again starts from the first question."
            )
        sys.exit("stopped. Run the same command again to carry on where it left off.")
    except LLMError as e:
        sys.exit(f"the model failed: {e}. Is Ollama running (ollama list)?")
    except evaluate.MissingAnswers as e:
        sys.exit(f"no saved answer for: {e}. Run `uv run fastbreak questions freeze` first.")


def ask_command(args):
    llm = Ollama(args.model, think=args.think)
    result = ask(args.question, llm, args.db)
    traces.record(traces.connect(args.traces), result, llm.name, "ask")
    print(f"SQL:\n{result.sql}\n")
    if result.error:
        sys.exit(result.error)
    print(f"Rows ({', '.join(result.columns)}):")
    for row in result.rows[:20]:
        print(f"  {row}")
    if len(result.rows) > 20 or result.truncated:
        print("  ...")
    if result.answer is None:
        missing = ", ".join(f"{n:g}" for n in result.ungrounded)
        print(f"\nNo answer: the model's reply used numbers that aren't in the rows ({missing}).")
    else:
        print(f"\n{result.answer}")
    print(f"\n({result.seconds:.1f}s, {len(result.calls)} model calls)")


def eval_command(conn, args):
    questions = evals.load_questions()
    if args.id:
        unknown = set(args.id) - {q.id for q in questions}
        if unknown:
            sys.exit(f"no such question: {', '.join(sorted(unknown))}")
        questions = [q for q in questions if q.id in args.id]
        unapproved = [q.id for q in questions if q.status != "approved"]
        if unapproved:
            sys.exit(f"not approved, so not scored: {', '.join(unapproved)}")
    s = evaluate.run(
        conn,
        Ollama(args.model, think=args.think),
        args.db,
        questions,
        trace_db=traces.connect(args.traces),
    )
    low, high = s["accuracy_95"]
    print(
        f"\n{s['model']}: {s['correct']}/{s['questions']} correct ({s['accuracy']:.0%}, "
        f"95% range {low:.0%}-{high:.0%})"
    )
    print(
        f"query failed: {s['query_failed']}; replies cut off: {s['cut_off']}; "
        f"answers sent: {s['grounded']}, "
        f"of which wrong: {s['grounded_and_wrong']}"
    )
    print("by kind: " + ", ".join(f"{k} {v}" for k, v in s["by"].items()))
    print(
        f"latency p50 {s['p50_seconds']:.1f}s, p95 {s['p95_seconds']:.1f}s; "
        f"tokens in {s['prompt_tokens']:,}, out {s['output_tokens']:,}"
    )
    if s["correct"]:
        print(
            f"per correct answer: {s['seconds_per_correct']:.1f}s of model time, "
            f"{s['output_tokens_per_correct']:,} output tokens"
        )
    print(f"saved {s['saved']}")


def metrics_command(conn, args):
    rows = metrics.latency(traces.connect(args.traces), args.source)
    print("latency per step (seconds)")
    if not rows:
        print("  no traces yet: they're recorded by `fastbreak ask` and `fastbreak eval`")
    print(f"  {'model':<22} {'step':<10} {'count':>6} {'p50':>7} {'p95':>7}")
    for model, step, count, p50, p95 in rows:
        print(f"  {model:<22} {step:<10} {count:>6} {p50:>7.2f} {p95:>7.2f}")

    print("\ncost per correct answer, by eval run")
    print(
        f"  {'run':<20} {'model':<24} {'correct':>8} {'model s':>8} {'s/right':>8} {'tok/right':>10}"
    )
    for r in metrics.cost():
        mark = "" if r["finished"] else "  (stopped part-way)"
        per = (
            f"{r['seconds_per_correct']:>8.1f} {r['output_tokens_per_correct']:>10,.0f}"
            if r["correct"]
            else f"{'-':>8} {'-':>10}"
        )
        stamp, model = r["run"][:18], r["model"][:24]
        print(
            f"  {stamp:<20} {model:<24} {r['correct']:>3}/{r['questions']:<4} "
            f"{r['seconds']:>8.0f} {per}{mark}"
        )

    steps, runs, reasons = metrics.pipeline(conn)
    print("\npipeline failures, per game step (all time)")
    for step, games, failed, retried in steps:
        print(
            f"  {step:<9} {games:>7,} games, {failed:>4} failed ({failed / games:.2%}), "
            f"{retried:>4} needed a retry ({retried / games:.2%})"
        )
    print("\npipeline runs, last 30 days")
    for kind, count, ok, failed, running in runs:
        print(
            f"  {kind:<9} {count:>3} runs, {ok:>3} ok, {failed:>3} failed "
            f"({failed / count:.0%}), {running} still marked running"
        )
        for reason_kind, reason, n in reasons:
            if reason_kind == kind:
                print(f"    {n:>3} {reason}")


def print_status(conn):
    steps, runs = run.status(conn)
    print("step      status   games")
    for step, state, count in steps:
        print(f"{step:<9} {state:<8} {count:>6,}")
    print("\nrecent runs")
    for run_id, kind, started, finished, state, error in runs:
        print(f"#{run_id} {kind:<9} {state:<8} {started} -> {finished or '...'}  {error or ''}")


def questions_command(conn, args):
    questions = evals.load_questions()
    by_id = {q.id: q for q in questions}
    if args.action == "check":
        results = evals.check(conn, questions)
        for q, problem in results:
            print(f"{'ok ' if problem is None else 'BAD'} {q.status:<8} {q.id}  {problem or ''}")
        approved = sum(q.status == "approved" for q in questions)
        bad = sum(problem is not None for _, problem in results)
        print(f"\n{len(questions)} questions, {approved} approved, {bad} with problems")
        if bad:
            sys.exit(1)
    elif args.action == "freeze":
        if args.id:
            q = by_id[args.id]
            if q.status == "approved":
                sys.exit(f"{q.id} is approved. Set it back to draft first if the answer is wrong.")
            targets = [q]
        else:
            targets = [q for q in questions if q.frozen and evals.frozen_answer(q) is None]
        for q in targets:
            rows = evals.freeze(conn, q)
            print(f"saved {q.id}: {len(rows)} row(s)")
        print(f"{len(targets)} answer(s) saved in {evals.ANSWERS}/")
    else:
        q = by_id[args.id]
        print(f"{q.id}  [{q.category}, {q.difficulty}, {q.status}]\n\n{q.question}\n")
        if q.notes:
            print(f"notes: {q.notes}\n")
        print(q.sql.strip() + "\n")
        saved = evals.frozen_answer(q)
        rows = saved if saved is not None else evals.run_sql(conn, q.sql)
        print("saved answer:" if saved is not None else "answer (not saved yet):")
        for row in rows:
            print("  ", row)
