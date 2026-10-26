"""The `fastbreak` command: uv run fastbreak <load-seasons | boxscores | nightly | status | questions | ask | eval | serve>."""

import argparse
import os
import signal
import sys

import uvicorn

from fastbreak import evals
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

    serve = commands.add_parser("serve", help="run the API the web app calls")
    serve.add_argument(
        "--host", default="127.0.0.1", help="address to listen on (default 127.0.0.1)"
    )
    serve.add_argument("--port", type=int, default=8077, help="port (default 8077)")

    args = parser.parse_args()
    if args.command == "serve":
        serve_command(args)
        return
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
        else:
            print_status(conn)
    except run.RunInProgress as e:
        sys.exit(f"{e}. Stop it first, or wait for it to finish (uv run fastbreak status).")
    except KeyboardInterrupt:
        sys.exit("stopped. Run the same command again to carry on where it left off.")
    except LLMError as e:
        sys.exit(f"the model failed: {e}. Is Ollama running (ollama list)?")


def serve_command(args):
    """Model, thinking and API key come from FASTBREAK_MODEL, FASTBREAK_THINK and FASTBREAK_API_KEY."""
    os.environ.setdefault("FASTBREAK_DB", args.db)
    uvicorn.run("fastbreak.api.app:app_from_env", factory=True, host=args.host, port=args.port)


def ask_command(args):
    result = ask(args.question, Ollama(args.model, think=args.think), args.db)
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
    s = evaluate.run(conn, Ollama(args.model, think=args.think), args.db, questions)
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
    print(f"saved {s['saved']}")


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
