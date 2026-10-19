import json
import os
import signal
import time
from datetime import date
from pathlib import Path

import pytest

from fastbreak import cli
from fastbreak.db import connect, init_db
from fastbreak.pipeline import run
from fastbreak.pipeline.fetch import FetchError

FIXTURES = Path(__file__).parent / "fixtures"
GAMES = ["0022400061", "0022400071", "0022400147"]  # opening night, overtime, Mexico City
EMPTY = {"resultSets": [{"headers": [], "rowSet": []}]}


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


class FakeFetcher:
    """Serves the 2024-25 fixtures. Can fail for chosen games, or crash after N box scores."""

    def __init__(self, failing=(), crash_after=None):
        self.failing = set(failing)
        self.crash_after = crash_after
        self.boxscore_calls = []

    def get(self, endpoint_cls, refresh=False, **params):
        name = endpoint_cls.__name__
        if name == "LeagueGameLog":
            if (params["season"], params["season_type_all_star"]) != ("2024-25", "Regular Season"):
                return EMPTY
            kind = "teams" if params["player_or_team_abbreviation"] == "T" else "players"
            return fixture(f"gamelog_{kind}.json")
        if name == "ScoreboardV3":
            return fixture(f"scoreboard_{params['game_date']}.json")
        game_id = params["game_id"]
        if self.crash_after is not None and len(self.boxscore_calls) == self.crash_after:
            raise KeyboardInterrupt  # the process dies: power cut, Ctrl-C, OOM
        self.boxscore_calls.append(game_id)
        if game_id in self.failing:
            raise FetchError(f"BoxScoreTraditionalV3 failed after 5 attempts: {game_id}")
        return fixture(f"boxscore_{game_id}.json")


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    yield conn
    conn.close()


def steps(db, step):
    rows = db.execute(
        "SELECT game_id, status, attempts, last_error FROM game_ingest WHERE step = ?", (step,)
    )
    return {gid: (status, attempts, error) for gid, status, attempts, error in rows}


def test_seasons_run_from_first_to_current():
    assert run.seasons_from("2023-24", today=date(2026, 3, 1)) == ["2023-24", "2024-25", "2025-26"]
    assert run.seasons_from("2025-26", today=date(2026, 10, 16))[-1] == "2026-27"


def test_loading_a_season_marks_every_game_done(db):
    assert run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season") == (3, 0)
    assert {gid: s[0] for gid, s in steps(db, "gamelog").items()} == dict.fromkeys(GAMES, "done")


def test_a_broken_game_fails_alone(db, monkeypatch):
    original = run.transform.player_stats

    def break_mexico_city(rows):
        if rows and rows[0]["GAME_ID"] == "0022400147":
            rows = [{**rows[0], "PTS": -1}, *rows[1:]]
        return original(rows)

    monkeypatch.setattr(run.transform, "player_stats", break_mexico_city)
    assert run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season") == (2, 1)
    status, _, error = steps(db, "gamelog")["0022400147"]
    assert status == "failed"
    assert "greater than or equal to 0" in error
    assert db.execute("SELECT COUNT(*) FROM games WHERE game_id = '0022400147'").fetchone()[0] == 0


def test_boxscores_set_starters_and_exact_seconds(db):
    run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season")
    assert run.ingest_boxscores(db, FakeFetcher(), log=lambda _: None) == (3, 0)
    starters = db.execute(
        "SELECT game_id, team_id, SUM(starter) FROM player_game_stats GROUP BY game_id, team_id"
    ).fetchall()
    assert len(starters) == 6
    assert all(count == 5 for _, _, count in starters)
    brown = db.execute(  # Jaylen Brown played 29:54 on opening night
        "SELECT seconds FROM player_game_stats WHERE game_id = '0022400061' AND player_id = 1627759"
    ).fetchone()[0]
    assert brown == 29 * 60 + 54


def test_reloading_the_game_log_keeps_box_score_seconds(db):
    run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season")
    run.ingest_boxscores(db, FakeFetcher(), log=lambda _: None)
    run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season")  # nightly correction run
    brown = db.execute(
        "SELECT starter, seconds FROM player_game_stats"
        " WHERE game_id = '0022400061' AND player_id = 1627759"
    ).fetchone()
    assert brown == (1, 29 * 60 + 54)


def test_a_crashed_run_resumes_without_refetching(db):
    run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season")
    first = FakeFetcher(crash_after=2)
    with pytest.raises(KeyboardInterrupt):
        run.ingest_boxscores(db, first, log=lambda _: None)
    assert len(steps(db, "boxscore")) == 2

    second = FakeFetcher()
    run.ingest_boxscores(db, second, log=lambda _: None)
    assert len(second.boxscore_calls) == 1  # only the game the crash left behind
    assert set(second.boxscore_calls).isdisjoint(first.boxscore_calls)
    assert {s[0] for s in steps(db, "boxscore").values()} == {"done"}


def test_a_failing_game_is_recorded_and_the_run_continues(db):
    run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season")
    assert run.ingest_boxscores(db, FakeFetcher(failing={"0022400071"}), log=lambda _: None) == (
        2,
        1,
    )
    status, attempts, error = steps(db, "boxscore")["0022400071"]
    assert (status, attempts) == ("failed", 1)
    assert "failed after 5 attempts" in error


def test_failed_games_are_retried_up_to_the_limit(db):
    run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season")
    always_fails = FakeFetcher(failing={"0022400071"})
    for _ in range(run.MAX_ATTEMPTS + 1):
        run.ingest_boxscores(db, always_fails, log=lambda _: None)
    assert always_fails.boxscore_calls.count("0022400071") == run.MAX_ATTEMPTS
    assert steps(db, "boxscore")["0022400071"][1] == run.MAX_ATTEMPTS


def test_it_stops_after_too_many_failures_in_a_row(db):
    run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season")
    blocked = FakeFetcher(failing=GAMES)
    run.ingest_boxscores(db, blocked, max_failures_in_row=2, log=lambda _: None)
    assert len(blocked.boxscore_calls) == 2
    last_run = db.execute("SELECT status, error FROM ingest_runs ORDER BY run_id DESC").fetchone()
    assert last_run[0] == "failed"
    assert "probably blocked" in last_run[1]


def last_run(db):
    return db.execute("SELECT status, error FROM ingest_runs ORDER BY run_id DESC").fetchone()


def test_a_stopped_run_records_that_it_was_interrupted(db):
    run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season")
    with pytest.raises(KeyboardInterrupt):
        run.ingest_boxscores(db, FakeFetcher(crash_after=1), log=lambda _: None)
    status, error = last_run(db)
    assert status == "failed"
    assert error.startswith("interrupted")


def test_a_crashed_run_records_why(db, monkeypatch):
    run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season")

    def broken(conn, updates):
        raise RuntimeError("disk full")

    monkeypatch.setattr(run, "apply_boxscore", broken)
    with pytest.raises(RuntimeError):
        run.ingest_boxscores(db, FakeFetcher(), log=lambda _: None)
    assert last_run(db) == ("failed", "crashed: RuntimeError: disk full")


def test_blocked_keeps_its_reason_instead_of_ok(db):
    run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season")
    run.ingest_boxscores(db, FakeFetcher(failing=GAMES), max_failures_in_row=2, log=lambda _: None)
    assert "probably blocked" in last_run(db)[1]


def test_a_second_run_is_refused_while_one_is_going(db):
    run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season")
    second = FakeFetcher()
    with run.tracked_run(db, "boxscores"), pytest.raises(run.RunInProgress):
        run.ingest_boxscores(db, second, log=lambda _: None)
    assert second.boxscore_calls == []
    assert db.execute("SELECT COUNT(*) FROM ingest_runs WHERE kind = 'boxscores'").fetchone() == (
        1,
    )


def test_a_run_left_running_by_a_dead_process_is_closed_by_the_next_one(db):
    run.ingest_season(db, FakeFetcher(), "2024-25", "Regular Season")
    dead = run.start_run(db, "boxscores")  # kill -9 or a power cut: nothing recorded the end
    run.ingest_boxscores(db, FakeFetcher(), log=lambda _: None)
    status, finished, error = db.execute(
        "SELECT status, finished_at, error FROM ingest_runs WHERE run_id = ?", (dead,)
    ).fetchone()
    assert (status, finished is not None) == ("failed", True)
    assert "process died" in error
    assert last_run(db) == ("ok", None)


def test_kill_stops_a_run_like_ctrl_c():
    previous = signal.getsignal(signal.SIGTERM)
    try:
        cli.stop_on_sigterm()
        with pytest.raises(KeyboardInterrupt):
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(1)  # the handler runs here, almost immediately
    finally:
        signal.signal(signal.SIGTERM, previous)
