import json
from pathlib import Path

import pytest

from fastbreak.db import connect, init_db
from fastbreak.pipeline import transform
from fastbreak.pipeline.load import load_season

FIXTURES = Path(__file__).parent / "fixtures"
NEUTRAL, WAS = "0022400147", 1610612764


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def season():
    team_rows = transform.result_rows(json.loads((FIXTURES / "gamelog_teams.json").read_text()))
    player_rows = transform.result_rows(json.loads((FIXTURES / "gamelog_players.json").read_text()))
    return {
        "teams": transform.teams(team_rows),
        "players": transform.players(player_rows),
        "games": transform.games(team_rows, "2024-25", {NEUTRAL: WAS}),
        "stats": transform.player_stats(player_rows),
    }


def counts(db):
    return {
        t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("teams", "players", "games", "player_game_stats")
    }


def test_load_saves_every_row(db, season):
    load_season(db, **season)
    assert counts(db) == {
        "teams": 6,
        "players": len(season["players"]),
        "games": 3,
        "player_game_stats": 70,
    }


def test_loading_twice_does_not_duplicate(db, season):
    load_season(db, **season)
    first = counts(db)
    load_season(db, **season)
    assert counts(db) == first


def test_a_correction_updates_the_stat(db, season):
    load_season(db, **season)
    game_id, player_id = season["stats"][0][:2]
    corrected = list(season["stats"][0])
    corrected[19] += 2  # the NBA added a basket the next day
    load_season(db, **{**season, "stats": [tuple(corrected)]})
    pts = db.execute(
        "SELECT pts FROM player_game_stats WHERE game_id = ? AND player_id = ?",
        (game_id, player_id),
    ).fetchone()[0]
    assert pts == corrected[19]


def test_reload_keeps_starter_from_the_box_score(db, season):
    load_season(db, **season)
    db.execute("UPDATE player_game_stats SET starter = 1")  # as the box score step would
    load_season(db, **season)  # the game log always sends starter = NULL
    unknown = db.execute("SELECT COUNT(*) FROM player_game_stats WHERE starter IS NULL")
    assert unknown.fetchone()[0] == 0


def test_a_bad_row_saves_nothing(db, season):
    broken = list(season["stats"][0])
    broken[0] = "0099999999"  # a game that doesn't exist: the foreign key rejects it
    with pytest.raises(Exception, match="FOREIGN KEY"):
        load_season(db, **{**season, "stats": season["stats"] + [tuple(broken)]})
    assert counts(db) == {"teams": 0, "players": 0, "games": 0, "player_game_stats": 0}
