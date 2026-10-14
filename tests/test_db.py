import sqlite3

import pytest

from fastbreak.db import connect, init_db

GAME = "0022400061"
INSERT_STAT = "INSERT INTO player_game_stats VALUES (" + ", ".join(["?"] * 21) + ")"
UPSERT_STAT = INSERT_STAT + " ON CONFLICT (game_id, player_id) DO UPDATE SET pts = excluded.pts"


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    yield conn
    conn.close()


def seed(db):
    """Add one team, player and game, so stat rows have something to point at."""
    db.execute("INSERT INTO teams VALUES (1610612747, 'LAL', 'Los Angeles Lakers')")
    db.execute("INSERT INTO players VALUES (2544, 'LeBron James')")
    db.execute(
        "INSERT INTO games (game_id, season, season_type, game_date, home_team_id,"
        " away_team_id, home_pts, away_pts) VALUES (?, '2024-25', 'Regular Season',"
        " '2024-10-22', 1610612747, 1610612747, 110, 103)",
        (GAME,),
    )


def stat_row(game_id=GAME, pts=20):
    """A complete 21-column row: game, player, team, starter, seconds, 15 stats, plus/minus."""
    return (game_id, 2544, 1610612747, 1, 2100, *[0] * 14, pts, 5)


def test_create_database_twice(db):
    init_db(db)  # IF NOT EXISTS means this must not raise


def test_foreign_keys_enforced(db):
    seed(db)
    db.execute(INSERT_STAT, stat_row())  # a valid row goes in
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        db.execute(INSERT_STAT, stat_row(game_id="0099999999"))  # only the game is wrong


def test_reload_does_not_duplicate(db):
    seed(db)
    db.execute(UPSERT_STAT, stat_row(pts=10))
    db.execute(UPSERT_STAT, stat_row(pts=20))  # the NBA corrected the stat
    assert db.execute("SELECT COUNT(*) FROM player_game_stats").fetchone()[0] == 1
    assert db.execute("SELECT pts FROM player_game_stats").fetchone()[0] == 20
