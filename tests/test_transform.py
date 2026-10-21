import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fastbreak.pipeline import transform

FIXTURES = Path(__file__).parent / "fixtures"
NORMAL, NEUTRAL, OVERTIME = (
    "0022400061",
    "0022400147",
    "0022400071",
)  # NYK at BOS (opening night), MIA-WAS in Mexico City, PHX at LAC (overtime)
WAS, MIA = 1610612764, 1610612748


def load(name):
    return transform.result_rows(json.loads((FIXTURES / name).read_text()))


@pytest.fixture
def team_rows():
    return load("gamelog_teams.json")


@pytest.fixture
def player_rows():
    return load("gamelog_players.json")


GAME_FIELDS = list(transform.GameRow.model_fields)
STAT_FIELDS = list(transform.StatRow.model_fields)


def all_games(rows):
    return [dict(zip(GAME_FIELDS, g)) for g in transform.games(rows, "2024-25", {NEUTRAL: WAS})]


def game(rows, game_id):
    return next(g for g in all_games(rows) if g["game_id"] == game_id)


def test_result_rows_are_dicts_keyed_by_header(player_rows):
    assert len(player_rows) == 70
    assert {"GAME_ID", "PLAYER_ID", "PTS", "MIN"} <= player_rows[0].keys()


def test_home_and_away_come_from_matchup(team_rows):
    opening_night = game(team_rows, NORMAL)  # "BOS vs. NYK"
    assert opening_night["home_team_id"] == 1610612738
    assert opening_night["away_team_id"] == 1610612752
    assert opening_night["is_neutral"] is False
    assert opening_night["season_type"] == "Regular Season"


def test_neutral_site_game_uses_the_lookup(team_rows):
    assert transform.neutral_game_ids(team_rows) == {NEUTRAL}
    mexico_city = game(team_rows, NEUTRAL)
    assert (mexico_city["home_team_id"], mexico_city["away_team_id"]) == (WAS, MIA)
    assert mexico_city["is_neutral"] is True


def test_neutral_site_game_without_lookup_fails_loudly(team_rows):
    with pytest.raises(ValueError, match="neutral site"):
        transform.games(team_rows, "2024-25", neutral_home={})


def test_overtimes_from_team_minutes(team_rows):
    assert game(team_rows, OVERTIME)["overtimes"] == 1
    assert game(team_rows, NORMAL)["overtimes"] == 0


def test_one_stat_row_per_player_per_game(player_rows):
    stats = transform.player_stats(player_rows)
    assert len(stats) == len(player_rows)
    assert len({(s[0], s[1]) for s in stats}) == len(stats)
    assert all(len(s) == 21 for s in stats)


def test_seconds_and_unknown_starter(player_rows):
    first = player_rows[0]
    stat = dict(zip(STAT_FIELDS, transform.player_stats([first])[0]))
    assert stat["seconds"] == first["MIN"] * 60
    assert stat["starter"] is None


def test_player_points_add_up_to_team_score(player_rows, team_rows):
    stats = [dict(zip(STAT_FIELDS, s)) for s in transform.player_stats(player_rows)]

    def points(game_id, team_id):
        return sum(s["pts"] for s in stats if (s["game_id"], s["team_id"]) == (game_id, team_id))

    for g in all_games(team_rows):
        assert points(g["game_id"], g["home_team_id"]) == g["home_pts"]
        assert points(g["game_id"], g["away_team_id"]) == g["away_pts"]


def test_negative_stat_is_rejected(player_rows):
    bad = {**player_rows[0], "PTS": -3}
    with pytest.raises(ValidationError):
        transform.player_stats([bad])


def test_play_in_and_all_star_are_skipped(team_rows):
    play_in = {**team_rows[0], "SEASON_ID": "52024"}
    all_star = {**team_rows[0], "SEASON_ID": "32024"}
    assert transform.kept([play_in, all_star, team_rows[1]]) == [team_rows[1]]


def test_a_game_still_being_played_is_skipped(team_rows, player_rows):
    # opening night 2026-27, fetched in the first quarter: no result yet, 0 team minutes
    live_team = {**team_rows[0], "WL": None, "MIN": 0}
    live_player = {**player_rows[0], "WL": None}
    assert transform.kept([live_team, team_rows[1]]) == [team_rows[1]]
    assert transform.kept([live_player, player_rows[1]]) == [player_rows[1]]


def test_teams_and_players_are_unique(team_rows, player_rows):
    assert len(transform.teams(team_rows)) == 6
    ids = [p[0] for p in transform.players(player_rows)]
    assert len(ids) == len(set(ids))
