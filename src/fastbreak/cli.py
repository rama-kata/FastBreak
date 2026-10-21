"""The `fastbreak` command: uv run fastbreak <load-seasons | boxscores | nightly | status | questions>."""

import argparse
import signal
import sys

from fastbreak import evals
from fastbreak.db import connect, init_db
from fastbreak.pipeline import run
from fastbreak.pipeline.fetch import Fetcher

DB_PATH = "data/nba.db"
CACHE_DIR = "data/raw"


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
        else:
            print_status(conn)
    except run.RunInProgress as e:
        sys.exit(f"{e}. Stop it first, or wait for it to finish (uv run fastbreak status).")
    except KeyboardInterrupt:
        sys.exit("stopped. Run the same command again to carry on where it left off.")


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
