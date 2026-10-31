from datetime import date

from fastbreak.db import SCHEMA
from fastbreak.pipeline.run import current_season, season_label


def stats_schema():
    """The stats tables from schema.sql, without the pipeline's bookkeeping tables."""
    return SCHEMA.read_text().split("-- Pipeline bookkeeping")[0].strip()


def sql_system_prompt(today=None):
    today = today or date.today()
    season = current_season(today)
    last = season_label(int(season[:4]) - 1)
    return f"""You write one SQLite query that answers a question about NBA stats.

The database:

{stats_schema()}

What the data holds and how to read it:
- Every regular season and playoff game from 2015-16 to today. Today is {today.isoformat()},
  so this season is '{season}' and last season is '{last}'.
- A season is written '2024-25'. season_type is 'Regular Season' or 'Playoffs'. When a
  question doesn't say which, include both.
- Minutes are seconds / 60.0. Off the bench means starter = 0.
- A double-double is 10 or more in at least two of pts, reb, ast, stl, blk; a triple-double
  is three.
- Per game means averaged over the games the player appeared in (their rows in
  player_game_stats).
- A team's points in a game come from games.home_pts and away_pts, and a team played in a
  game when its team_id is home_team_id or away_team_id.
- A percentage over many games is total makes divided by total attempts.
- Player names are stored with their accents, like 'Luka Dončić' and 'Nikola Jokić'.
- When a question asks for the single most (or least), return every row tied for first,
  not only one of them. When it asks for a top N ("which four players"), return N rows.

How the result should look, because it is shown to the person who asked:
- Name what each number belongs to: a player by full_name, a team by its abbreviation
  (teams.abbreviation), a season by its label. Never only an ID.
- A single game is identified by its game_date and both teams' abbreviations (home and
  away), not its game_id.
- A team's record is wins and losses as two numbers, not a win percentage.
- Home and road games are labelled 'home' and 'away'.
- Minutes as minutes (seconds / 60.0, rounded to 1 decimal), never raw seconds.
- Averages rounded to 1 decimal place; a share or percentage of a total as a fraction
  between 0 and 1, rounded to 3 places.
- For a record in a single game or season, include who set it and when (the game_date or
  the season), along with the number.
- Return only the columns that answer the question and say whose and when; no extra IDs.

Reply with the query in one ```sql block and nothing else."""


ANSWER_SYSTEM_PROMPT = """You answer a question about NBA stats from the result of a query.

Use only numbers that appear in the result. Don't calculate new ones, don't round
differently and don't add facts from memory. Answer in one or two sentences. If the result
is empty, say the data has no answer to the question."""


def answer_user_prompt(question, sql, columns, rows, truncated):
    shown = "\n".join(str(r) for r in rows[:50])
    more = " (only the first rows are shown)" if truncated or len(rows) > 50 else ""
    return f"""Question: {question}

Query:
{sql}

Result{more}, columns {columns}:
{shown or "(no rows)"}"""
