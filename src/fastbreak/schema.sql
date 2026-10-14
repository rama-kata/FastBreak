CREATE TABLE IF NOT EXISTS teams (
    team_id       INTEGER PRIMARY KEY,
    abbreviation  TEXT NOT NULL,
    name          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    player_id  INTEGER PRIMARY KEY,
    full_name  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    game_id       TEXT PRIMARY KEY,                -- text: leading zeros
    season        TEXT NOT NULL,                   -- '2024-25'
    season_type   TEXT NOT NULL CHECK (season_type IN ('Regular Season', 'Playoffs')),
    game_date     TEXT NOT NULL,                   -- 'YYYY-MM-DD'
    home_team_id  INTEGER NOT NULL REFERENCES teams,
    away_team_id  INTEGER NOT NULL REFERENCES teams,
    is_neutral    INTEGER NOT NULL DEFAULT 0,
    home_pts      INTEGER NOT NULL,
    away_pts      INTEGER NOT NULL,
    overtimes     INTEGER NOT NULL DEFAULT 0       -- from team minutes: 240 = 0, 265 = 1
);

CREATE TABLE IF NOT EXISTS player_game_stats (
    game_id     TEXT NOT NULL REFERENCES games,
    player_id   INTEGER NOT NULL REFERENCES players,
    team_id     INTEGER NOT NULL REFERENCES teams,  -- per game: players get traded
    starter     INTEGER,                            -- NULL until the box score is loaded
    seconds     INTEGER NOT NULL,                   -- fits both whole minutes and MM:SS
    fgm INTEGER NOT NULL, fga INTEGER NOT NULL,
    fg3m INTEGER NOT NULL, fg3a INTEGER NOT NULL,
    ftm INTEGER NOT NULL, fta INTEGER NOT NULL,
    oreb INTEGER NOT NULL, dreb INTEGER NOT NULL, reb INTEGER NOT NULL,
    ast INTEGER NOT NULL, stl INTEGER NOT NULL, blk INTEGER NOT NULL,
    tov INTEGER NOT NULL, pf INTEGER NOT NULL, pts INTEGER NOT NULL,
    plus_minus  INTEGER,
    PRIMARY KEY (game_id, player_id)                -- what makes reloading safe
);

CREATE INDEX IF NOT EXISTS idx_stats_player ON player_game_stats (player_id);
CREATE INDEX IF NOT EXISTS idx_games_season ON games (season, season_type);
CREATE INDEX IF NOT EXISTS idx_games_date ON games (game_date);

-- Pipeline bookkeeping
CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL,                    -- 'season', 'nightly', 'boxscores'
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    status       TEXT NOT NULL CHECK (status IN ('running', 'ok', 'failed')),
    error        TEXT
);

CREATE TABLE IF NOT EXISTS game_ingest (
    game_id     TEXT NOT NULL,
    step        TEXT NOT NULL,                     -- 'gamelog', 'boxscore'
    status      TEXT NOT NULL CHECK (status IN ('pending', 'done', 'failed')),
    attempts    INTEGER NOT NULL DEFAULT 0,
    last_error  TEXT,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (game_id, step)
);

CREATE TABLE IF NOT EXISTS data_version (
    id          INTEGER PRIMARY KEY CHECK (id = 1), -- always exactly one row
    version     INTEGER NOT NULL,
    updated_at  TEXT NOT NULL
);
