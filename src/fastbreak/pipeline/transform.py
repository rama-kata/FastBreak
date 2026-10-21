"""Turn LeagueGameLog responses into rows for our tables. No database, no network."""

from collections import defaultdict

from pydantic import BaseModel, Field

# The first digit of SEASON_ID is the season type. v1 skips Play-In (5) and All-Star (3).
SEASON_TYPES = {"2": "Regular Season", "4": "Playoffs"}
REGULATION_MINUTES = 240  # 5 players x 48 minutes
OVERTIME_MINUTES = 25  # 5 players x 5 minutes

GAME_ID = Field(pattern=r"^\d{10}$")
COUNT = Field(ge=0)


class GameRow(BaseModel):
    game_id: str = GAME_ID
    season: str = Field(pattern=r"^\d{4}-\d{2}$")
    season_type: str
    game_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    home_team_id: int
    away_team_id: int
    is_neutral: bool
    home_pts: int = COUNT
    away_pts: int = COUNT
    overtimes: int = COUNT


class StatRow(BaseModel):
    game_id: str = GAME_ID
    player_id: int
    team_id: int
    starter: bool | None  # unknown until the box score is loaded
    seconds: int = COUNT
    fgm: int = COUNT
    fga: int = COUNT
    fg3m: int = COUNT
    fg3a: int = COUNT
    ftm: int = COUNT
    fta: int = COUNT
    oreb: int = COUNT
    dreb: int = COUNT
    reb: int = COUNT
    ast: int = COUNT
    stl: int = COUNT
    blk: int = COUNT
    tov: int = COUNT
    pf: int = COUNT
    pts: int = COUNT
    plus_minus: int | None


def result_rows(data):
    """One dict per row of the response's first result set, keyed by the API's headers."""
    result = data["resultSets"][0]
    return [dict(zip(result["headers"], row)) for row in result["rowSet"]]


def season_type(row):
    """'Regular Season' or 'Playoffs', or None for game types v1 skips."""
    return SEASON_TYPES.get(str(row["SEASON_ID"])[0])


def kept(rows):
    """Drop Play-In, All-Star and anything else outside v1's scope, and unfinished games.

    The game log lists a game while it's still being played, with no result (WL) and
    partial stats. It's loaded the next time the game log is fetched after it ends.
    """
    return [row for row in rows if season_type(row) and row["WL"] is not None]


def teams(team_rows):
    """(team_id, abbreviation, name), once per team."""
    unique = {row["TEAM_ID"]: row for row in team_rows}
    return [(t["TEAM_ID"], t["TEAM_ABBREVIATION"], t["TEAM_NAME"]) for t in unique.values()]


def players(player_rows):
    """(player_id, full_name), once per player."""
    unique = {row["PLAYER_ID"]: row["PLAYER_NAME"] for row in player_rows}
    return list(unique.items())


def neutral_game_ids(team_rows):
    """Games where MATCHUP lists both teams as away, so home has to come from elsewhere."""
    by_game = _by_game(team_rows)
    return {gid for gid, rows in by_game.items() if not any(_is_home(r) for r in rows)}


def games(team_rows, season, neutral_home):
    """One row per game, built from its two team rows.

    neutral_home maps each neutral-site game to the team the NBA lists as home
    (from ScoreboardV3's gameCode).
    """
    out = []
    for gid, rows in _by_game(team_rows).items():
        if len(rows) != 2:
            raise ValueError(f"game {gid} has {len(rows)} team rows, expected 2")
        homes = [r for r in rows if _is_home(r)]
        if len(homes) == 1:
            home, is_neutral = homes[0], False
        elif not homes and gid in neutral_home:
            home = next(r for r in rows if r["TEAM_ID"] == neutral_home[gid])
            is_neutral = True
        elif not homes:
            raise ValueError(
                f"game {gid} is at a neutral site and has no home team in neutral_home"
            )
        else:
            raise ValueError(f"game {gid} lists both teams as home")
        away = rows[0] if rows[1] is home else rows[1]
        row = GameRow(
            game_id=gid,
            season=season,
            season_type=season_type(home),
            game_date=home["GAME_DATE"],
            home_team_id=home["TEAM_ID"],
            away_team_id=away["TEAM_ID"],
            is_neutral=is_neutral,
            home_pts=home["PTS"],
            away_pts=away["PTS"],
            overtimes=(home["MIN"] - REGULATION_MINUTES) // OVERTIME_MINUTES,
        )
        out.append(tuple(row.model_dump().values()))
    return out


def player_stats(player_rows):
    """One row per player per game, in player_game_stats column order."""
    out = []
    for r in player_rows:
        row = StatRow(
            game_id=r["GAME_ID"],
            player_id=r["PLAYER_ID"],
            team_id=r["TEAM_ID"],
            starter=None,
            seconds=r["MIN"] * 60,  # LeagueGameLog rounds to whole minutes
            fgm=r["FGM"],
            fga=r["FGA"],
            fg3m=r["FG3M"],
            fg3a=r["FG3A"],
            ftm=r["FTM"],
            fta=r["FTA"],
            oreb=r["OREB"],
            dreb=r["DREB"],
            reb=r["REB"],
            ast=r["AST"],
            stl=r["STL"],
            blk=r["BLK"],
            tov=r["TOV"],
            pf=r["PF"],
            pts=r["PTS"],
            plus_minus=r["PLUS_MINUS"],
        )
        out.append(tuple(row.model_dump().values()))
    return out


def boxscore_updates(data):
    """(starter, seconds, game_id, player_id) for every player who played.

    The box score is the only source for who started (the 5 players per team with a
    position) and for exact minutes, which LeagueGameLog rounds.
    """
    box = data["boxScoreTraditional"]
    out = []
    for side in ("homeTeam", "awayTeam"):
        team = box[side]
        played = [p for p in team["players"] if p["statistics"]["minutes"]]
        starters = sum(1 for p in played if p["position"])
        if starters != 5:
            raise ValueError(f"game {box['gameId']}: team {team['teamId']} has {starters} starters")
        for p in played:
            seconds = _seconds(p["statistics"]["minutes"])
            out.append((bool(p["position"]), seconds, box["gameId"], p["personId"]))
    return out


def _seconds(minutes):
    """'29:54' -> 1794. Anything else is a format change worth failing on."""
    mins, _, secs = minutes.partition(":")
    if not (mins.isdigit() and secs.isdigit()):
        raise ValueError(f"unexpected minutes format: {minutes!r}")
    return int(mins) * 60 + int(secs)


def by_game(rows):
    """Group game log rows by GAME_ID."""
    return _by_game(rows)


def _by_game(team_rows):
    grouped = defaultdict(list)
    for row in team_rows:
        grouped[row["GAME_ID"]].append(row)
    return grouped


def _is_home(team_row):
    return " vs. " in team_row["MATCHUP"]
