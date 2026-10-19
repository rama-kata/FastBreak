"""The `fastbreak` command: uv run fastbreak <load-seasons | boxscores | status>."""

import argparse
import signal
import sys

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

    commands.add_parser("status", help="show pipeline progress")

    args = parser.parse_args()
    conn = connect(args.db)
    init_db(conn)
    fetcher = Fetcher(CACHE_DIR)
    stop_on_sigterm()

    try:
        if args.command == "load-seasons":
            run.ingest_seasons(conn, fetcher, first=args.first)
        elif args.command == "boxscores":
            run.ingest_boxscores(conn, fetcher, limit=args.limit)
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
