"""Save transformed rows into SQLite. Loading the same data twice is always safe."""

STAT_COLUMNS = (
    "game_id, player_id, team_id, starter, seconds, fgm, fga, fg3m, fg3a, ftm, fta,"
    " oreb, dreb, reb, ast, stl, blk, tov, pf, pts, plus_minus"
)
STAT_VALUES = ["seconds", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb"]
STAT_VALUES += ["ast", "stl", "blk", "tov", "pf", "pts", "plus_minus", "team_id"]

UPSERT_TEAM = """
INSERT INTO teams (team_id, abbreviation, name) VALUES (?, ?, ?)
ON CONFLICT (team_id) DO UPDATE SET abbreviation = excluded.abbreviation, name = excluded.name
"""

UPSERT_PLAYER = """
INSERT INTO players (player_id, full_name) VALUES (?, ?)
ON CONFLICT (player_id) DO UPDATE SET full_name = excluded.full_name
"""

UPSERT_GAME = """
INSERT INTO games (game_id, season, season_type, game_date, home_team_id, away_team_id,
                   is_neutral, home_pts, away_pts, overtimes)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (game_id) DO UPDATE SET
    season = excluded.season, season_type = excluded.season_type,
    game_date = excluded.game_date, home_team_id = excluded.home_team_id,
    away_team_id = excluded.away_team_id, is_neutral = excluded.is_neutral,
    home_pts = excluded.home_pts, away_pts = excluded.away_pts, overtimes = excluded.overtimes
"""

# A correction can change any stat, so every one is updated. starter comes from the box
# score and the game log always sends NULL, so a reload must not wipe it out.
UPSERT_STAT = f"""
INSERT INTO player_game_stats ({STAT_COLUMNS}) VALUES ({", ".join(["?"] * 21)})
ON CONFLICT (game_id, player_id) DO UPDATE SET
    {", ".join(f"{c} = excluded.{c}" for c in STAT_VALUES)},
    starter = COALESCE(excluded.starter, player_game_stats.starter)
"""


def load_season(conn, teams, players, games, stats):
    """Upsert everything in one transaction, parents before children (foreign keys)."""
    with conn:
        conn.executemany(UPSERT_TEAM, teams)
        conn.executemany(UPSERT_PLAYER, players)
        conn.executemany(UPSERT_GAME, games)
        conn.executemany(UPSERT_STAT, stats)
