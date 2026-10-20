"""The pipeline: fetch, transform and load, with progress recorded so any run can resume."""

import fcntl
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta

from nba_api.stats.endpoints import boxscoretraditionalv3, leaguegamelog, scoreboardv3

from fastbreak.pipeline import transform
from fastbreak.pipeline.fetch import FetchError
from fastbreak.pipeline.load import apply_boxscore, load_season

SEASON_TYPES = ("Regular Season", "Playoffs")
MAX_ATTEMPTS = 3  # a game that fails this many times is left for a person to look at
# Each failed game has already been retried 5 times, so 2 in a row means NBA.com is blocking us.
MAX_FAILURES_IN_ROW = 2
# The NBA corrects stats within a day or two, so the nightly run re-checks this many days.
NIGHTLY_DAYS = 3


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def season_label(start_year):
    """2024 -> '2024-25'."""
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def seasons_from(first, today=None):
    """Every season from `first` up to the current one."""
    return [season_label(y) for y in range(int(first[:4]), int(current_season(today)[:4]) + 1)]


def current_season(today=None):
    """The season being played on `today`. A season starts in October."""
    today = today or date.today()
    return season_label(today.year if today.month >= 10 else today.year - 1)


def start_run(conn, kind):
    with conn:
        cur = conn.execute(
            "INSERT INTO ingest_runs (kind, started_at, status) VALUES (?, ?, 'running')",
            (kind, now()),
        )
    return cur.lastrowid


def finish_run(conn, run_id, status, error=None):
    """Record how a run ended. Only the first call counts, so the reason a run stopped isn't overwritten."""
    with conn:
        conn.execute(
            "UPDATE ingest_runs SET finished_at = ?, status = ?, error = ?"
            " WHERE run_id = ? AND status = 'running'",
            (now(), status, error, run_id),
        )


class RunInProgress(Exception):
    """Another run is already writing to this database."""


@contextmanager
def tracked_run(conn, kind):
    """One run at a time per database, and every run records how it ended.

    The lock is a flock on <db>.lock, which the OS releases when the process dies, even on kill -9.
    So whoever holds it knows any run still marked 'running' is dead, and closes those first.
    """
    path = conn.execute("PRAGMA database_list").fetchone()[2]
    with open(f"{path}.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RunInProgress(f"another run is already writing to {path}") from None
        with conn:
            conn.execute(
                "UPDATE ingest_runs SET finished_at = ?, status = 'failed',"
                " error = 'interrupted: the process died before recording how it ended'"
                " WHERE status = 'running'",
                (now(),),
            )
        run_id = start_run(conn, kind)
        try:
            yield run_id
        except KeyboardInterrupt:  # Ctrl-C, or kill / SIGTERM through the CLI's handler
            finish_run(conn, run_id, "failed", "interrupted: stopped by Ctrl-C or kill")
            raise
        except BaseException as e:
            finish_run(conn, run_id, "failed", f"crashed: {type(e).__name__}: {e}")
            raise
        finish_run(conn, run_id, "ok")


def mark(conn, game_id, step, status, error=None):
    """Record one attempt at a step for a game. attempts counts every try."""
    with conn:
        conn.execute(
            """
            INSERT INTO game_ingest (game_id, step, status, attempts, last_error, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT (game_id, step) DO UPDATE SET
                status = excluded.status, attempts = game_ingest.attempts + 1,
                last_error = excluded.last_error, updated_at = excluded.updated_at
            """,
            (game_id, step, status, error, now()),
        )


def neutral_homes(fetcher, team_rows):
    """Home team for each neutral-site game, from ScoreboardV3's gameCode (date/AWAYHOME)."""
    team_ids = {r["TEAM_ABBREVIATION"]: r["TEAM_ID"] for r in team_rows}
    homes = {}
    for game_id in transform.neutral_game_ids(team_rows):
        game_date = next(r["GAME_DATE"] for r in team_rows if r["GAME_ID"] == game_id)
        board = fetcher.get(scoreboardv3.ScoreboardV3, game_date=game_date)
        for game in board["scoreboard"]["games"]:
            if game["gameId"] == game_id:
                homes[game_id] = team_ids[game["gameCode"].split("/")[1][3:]]
    return homes  # a game missing here fails in transform.games(), loudly


def ingest_season(conn, fetcher, season, season_type, refresh=False):
    """Load one season's game logs. A broken game is marked failed; the rest still load.

    refresh skips the cache, for a season that is still being played.
    """
    params = {"season": season, "season_type_all_star": season_type, "refresh": refresh}
    team_rows = transform.kept(
        transform.result_rows(
            fetcher.get(leaguegamelog.LeagueGameLog, player_or_team_abbreviation="T", **params)
        )
    )
    player_rows = transform.kept(
        transform.result_rows(
            fetcher.get(leaguegamelog.LeagueGameLog, player_or_team_abbreviation="P", **params)
        )
    )
    if not team_rows:
        return 0, 0  # e.g. playoffs that haven't started yet

    neutral = neutral_homes(fetcher, team_rows)
    players_by_game = transform.by_game(player_rows)
    games, stats, failed = [], [], {}
    for game_id, rows in transform.by_game(team_rows).items():
        try:
            game_rows = transform.games(rows, season, neutral)
            stat_rows = transform.player_stats(players_by_game.get(game_id, []))
        except ValueError as e:  # pydantic's ValidationError is a ValueError too
            failed[game_id] = str(e)
            continue
        games += game_rows
        stats += stat_rows

    load_season(conn, transform.teams(team_rows), transform.players(player_rows), games, stats)
    for game_row in games:
        mark(conn, game_row[0], "gamelog", "done")
    for game_id, error in failed.items():
        mark(conn, game_id, "gamelog", "failed", error)
    return len(games), len(failed)


def ingest_seasons(conn, fetcher, first="2015-16", today=None, log=print):
    """Load every season's game logs from `first` to today."""
    with tracked_run(conn, "season") as run_id:
        try:
            for season in seasons_from(first, today):
                for season_type in SEASON_TYPES:
                    loaded, failed = ingest_season(conn, fetcher, season, season_type)
                    log(f"{season} {season_type}: {loaded} games loaded, {failed} failed")
        except FetchError as e:
            finish_run(conn, run_id, "failed", str(e))
            raise


def pending_boxscores(conn, limit=None):
    """Games with a loaded game log and no box score yet, newest first."""
    rows = conn.execute(
        """
        SELECT g.game_id FROM games g
        JOIN game_ingest gl ON gl.game_id = g.game_id AND gl.step = 'gamelog' AND gl.status = 'done'
        LEFT JOIN game_ingest bx ON bx.game_id = g.game_id AND bx.step = 'boxscore'
        WHERE bx.status IS NULL OR (bx.status = 'failed' AND bx.attempts < ?)
        ORDER BY g.game_date DESC, g.game_id DESC
        LIMIT ?
        """,
        (MAX_ATTEMPTS, -1 if limit is None else limit),
    )
    return [r[0] for r in rows]


def recent_games(conn, today, days):
    """Games played in the last `days` days up to today, newest first."""
    since = (today - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT game_id FROM games WHERE game_date >= ? ORDER BY game_date DESC, game_id DESC",
        (since,),
    )
    return [r[0] for r in rows]


def boxscore_done(conn, game_id):
    row = conn.execute(
        "SELECT status FROM game_ingest WHERE game_id = ? AND step = 'boxscore'", (game_id,)
    ).fetchone()
    return row is not None and row[0] == "done"


def load_boxscores(conn, fetcher, run_id, game_ids, max_failures_in_row, log, refresh=False):
    """Fetch and apply the box score for each game. Returns (done, failed, blocked).

    A game whose box score already loaded is never marked failed by a later re-fetch: its
    data is still good, the check for a correction just didn't get through this time.
    """
    done = failed = in_a_row = 0
    for game_id in game_ids:
        try:
            data = fetcher.get(
                boxscoretraditionalv3.BoxScoreTraditionalV3, refresh=refresh, game_id=game_id
            )
            apply_boxscore(conn, transform.boxscore_updates(data))
        except (FetchError, ValueError) as e:
            if not boxscore_done(conn, game_id):
                mark(conn, game_id, "boxscore", "failed", str(e))
            failed += 1
            if not isinstance(e, FetchError):
                continue  # the data itself is wrong; not a sign of being blocked
            in_a_row += 1  # NBA.com didn't answer, even after retries
            if in_a_row >= max_failures_in_row:
                error = f"stopped after {in_a_row} failed calls in a row: probably blocked"
                log(error)
                finish_run(conn, run_id, "failed", error)
                return done, failed, True
            continue
        mark(conn, game_id, "boxscore", "done")
        done += 1
        in_a_row = 0
        if done % 100 == 0:
            log(f"{done} box scores loaded, {failed} failed")
    return done, failed, False


def ingest_boxscores(conn, fetcher, limit=None, max_failures_in_row=MAX_FAILURES_IN_ROW, log=print):
    """Fill in starters and exact seconds. Resumes from whatever isn't done yet."""
    with tracked_run(conn, "boxscores") as run_id:
        done, failed, blocked = load_boxscores(
            conn, fetcher, run_id, pending_boxscores(conn, limit), max_failures_in_row, log
        )
        if not blocked:
            log(f"finished: {done} box scores loaded, {failed} failed")
        return done, failed


def ingest_nightly(
    conn, fetcher, today=None, days=NIGHTLY_DAYS, max_failures_in_row=MAX_FAILURES_IN_ROW, log=print
):
    """New games and corrections for the current season.

    The season's game log is re-fetched in full: it brings new games, and its upsert
    rewrites every stat, so a correction anywhere in the season lands too. Box scores are
    re-fetched for the last `days` days only, to load new games and catch corrected minutes.
    Older box scores that are still missing are left to `ingest_boxscores`.
    """
    today = today or date.today()
    season = current_season(today)
    with tracked_run(conn, "nightly") as run_id:
        try:
            for season_type in SEASON_TYPES:
                loaded, failed = ingest_season(conn, fetcher, season, season_type, refresh=True)
                log(f"{season} {season_type}: {loaded} games in the game log, {failed} failed")
        except FetchError as e:
            finish_run(conn, run_id, "failed", str(e))
            raise
        games = recent_games(conn, today, days)
        done, failed, blocked = load_boxscores(
            conn, fetcher, run_id, games, max_failures_in_row, log, refresh=True
        )
        if not blocked:
            log(f"finished: {done} box scores from the last {days} days loaded, {failed} failed")
        return done, failed


def status(conn):
    """Counts per step and status, plus the most recent runs."""
    steps = conn.execute(
        "SELECT step, status, COUNT(*) FROM game_ingest GROUP BY step, status ORDER BY step, status"
    ).fetchall()
    runs = conn.execute(
        "SELECT run_id, kind, started_at, finished_at, status, error"
        " FROM ingest_runs ORDER BY run_id DESC LIMIT 5"
    ).fetchall()
    return steps, runs
