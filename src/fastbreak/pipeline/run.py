"""The pipeline: fetch, transform and load, with progress recorded so any run can resume."""

from datetime import UTC, date, datetime

from nba_api.stats.endpoints import boxscoretraditionalv3, leaguegamelog, scoreboardv3

from fastbreak.pipeline import transform
from fastbreak.pipeline.fetch import FetchError
from fastbreak.pipeline.load import apply_boxscore, load_season

SEASON_TYPES = ("Regular Season", "Playoffs")
MAX_ATTEMPTS = 3  # a game that fails this many times is left for a person to look at


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def season_label(start_year):
    """2024 -> '2024-25'."""
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def seasons_from(first, today=None):
    """Every season from `first` up to the current one. A season starts in October."""
    today = today or date.today()
    current = today.year if today.month >= 10 else today.year - 1
    return [season_label(y) for y in range(int(first[:4]), current + 1)]


def start_run(conn, kind):
    with conn:
        cur = conn.execute(
            "INSERT INTO ingest_runs (kind, started_at, status) VALUES (?, ?, 'running')",
            (kind, now()),
        )
    return cur.lastrowid


def finish_run(conn, run_id, status, error=None):
    with conn:
        conn.execute(
            "UPDATE ingest_runs SET finished_at = ?, status = ?, error = ? WHERE run_id = ?",
            (now(), status, error, run_id),
        )


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


def ingest_season(conn, fetcher, season, season_type):
    """Load one season's game logs. A broken game is marked failed; the rest still load."""
    params = {"season": season, "season_type_all_star": season_type}
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
    run_id = start_run(conn, "season")
    try:
        for season in seasons_from(first, today):
            for season_type in SEASON_TYPES:
                loaded, failed = ingest_season(conn, fetcher, season, season_type)
                log(f"{season} {season_type}: {loaded} games loaded, {failed} failed")
    except FetchError as e:
        finish_run(conn, run_id, "failed", str(e))
        raise
    finish_run(conn, run_id, "ok")


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


def ingest_boxscores(conn, fetcher, limit=None, max_failures_in_row=10, log=print):
    """Fill in starters and exact seconds. Resumes from whatever isn't done yet."""
    run_id = start_run(conn, "boxscores")
    done = failed = in_a_row = 0
    for game_id in pending_boxscores(conn, limit):
        try:
            data = fetcher.get(boxscoretraditionalv3.BoxScoreTraditionalV3, game_id=game_id)
            apply_boxscore(conn, transform.boxscore_updates(data))
        except FetchError as e:  # NBA.com didn't answer, even after retries
            mark(conn, game_id, "boxscore", "failed", str(e))
            failed += 1
            in_a_row += 1
            if in_a_row >= max_failures_in_row:
                error = f"stopped after {in_a_row} failed calls in a row: probably blocked"
                log(error)
                finish_run(conn, run_id, "failed", error)
                return done, failed
            continue
        except ValueError as e:  # the data itself is wrong; not a sign of being blocked
            mark(conn, game_id, "boxscore", "failed", str(e))
            failed += 1
            continue
        mark(conn, game_id, "boxscore", "done")
        done += 1
        in_a_row = 0
        if done % 100 == 0:
            log(f"{done} box scores loaded, {failed} failed")
    log(f"finished: {done} box scores loaded, {failed} failed")
    finish_run(conn, run_id, "ok")
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
