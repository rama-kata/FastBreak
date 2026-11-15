"""Answering from the dbt semantic layer (data/semantic.duckdb) instead of nba.db.

The tables the agent sees, what each column means and the metric definitions all come
from dbt: column types from the built database, descriptions and metrics from dbt's
manifest. So the prompt says what the semantic layer's YAML says, and a definition
changes in one place. Build it first with `dbt build` in semantic/. Needs the `semantic`
dependency group (DuckDB).
"""

import json
import threading
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastbreak.agent.sql import MAX_ROWS, TIMEOUT_SECONDS, QueryError, QueryResult
from fastbreak.pipeline.run import current_season, season_label

SEMANTIC_DB = Path("data/semantic.duckdb")
MANIFEST = Path("semantic/target/manifest.json")
# Only the marts: the staging models are views into nba.db and don't work outside dbt.
MARTS = ("fct_games", "fct_team_games", "fct_player_games", "dim_players", "dim_teams")


def _connect(db_path):
    import duckdb

    # Read-only, and no file system: COPY TO, ATTACH, read_csv and INSTALL are refused.
    return duckdb.connect(str(db_path), read_only=True, config={"enable_external_access": False})


def _plain(value):
    """DuckDB returns dates and decimals; the scorer and grounding check expect text and
    floats, the way nba.db returns them."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def run_readonly(db_path, sql, max_rows=MAX_ROWS, timeout=TIMEOUT_SECONDS):
    """Run one query on the semantic layer, read-only, stopped after `timeout` seconds."""
    import duckdb

    if not sql:
        raise QueryError("the reply had no SQL in it")
    conn = _connect(db_path)
    timer = threading.Timer(timeout, conn.interrupt)
    timer.start()
    try:
        try:
            cursor = conn.execute(sql)
            rows = cursor.fetchmany(max_rows + 1)
        except duckdb.InterruptException as e:
            raise QueryError(f"the query ran longer than {timeout} seconds") from e
        except duckdb.Error as e:
            raise QueryError(str(e)) from e
        columns = [d[0] for d in cursor.description or []]
        kept = [tuple(_plain(v) for v in r) for r in rows[:max_rows]]
        return QueryResult(columns, kept, len(rows) > max_rows)
    finally:
        timer.cancel()
        conn.close()


def _manifest(path):
    return json.loads(Path(path).read_text())


def tables_text(db_path=SEMANTIC_DB, manifest_path=MANIFEST):
    """Each mart with its columns and types from the database, and its descriptions from
    dbt's manifest."""
    manifest = _manifest(manifest_path)
    models = {n["name"]: n for n in manifest["nodes"].values() if n["resource_type"] == "model"}
    conn = _connect(db_path)
    try:
        blocks = []
        for name in MARTS:
            node = models[name]
            docs = {
                c: " ".join(v.get("description", "").split()) for c, v in node["columns"].items()
            }
            cols = conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = ? ORDER BY ordinal_position",
                [name],
            ).fetchall()
            lines = [f"-- {' '.join(node['description'].split())}", f"{name} ("]
            for col, kind in cols:
                note = f"  -- {docs[col]}" if docs.get(col) else ""
                lines.append(f"    {col} {kind},{note}")
            lines.append(")")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)
    finally:
        conn.close()


def definitions_text(manifest_path=MANIFEST):
    """The metric definitions, from the metrics' YAML: a ratio is its numerator over its
    denominator; a total with a description says what it counts."""
    metrics = _manifest(manifest_path).get("metrics", {}).values()
    by_name = {m["name"]: m for m in metrics}
    lines = []
    for m in sorted(metrics, key=lambda m: m["name"]):
        label, desc = m["label"], (m.get("description") or "").strip()
        if m["type"] == "ratio":
            p = m["type_params"]
            num = by_name[p["numerator"]["name"]]["label"]
            den = by_name[p["denominator"]["name"]]["label"]
            lines.append(f"- {label}: total {num.lower()} / total {den.lower()}. {desc}".strip())
        elif desc:
            lines.append(f"- {label}: {desc}")
    return "\n".join(lines)


def sql_system_prompt(today=None, db_path=SEMANTIC_DB, manifest_path=MANIFEST):
    today = today or date.today()
    season = current_season(today)
    last = season_label(int(season[:4]) - 1)
    return f"""You write one DuckDB SQL query that answers a question about NBA stats.

The tables, from the stats semantic layer. After -- is what a column means:

{tables_text(db_path, manifest_path)}

Definitions, from the semantic layer. Use them, and use the columns above that already
hold a definition (minutes, off_bench, home_away, team_won, won, is_double_double,
is_triple_double) instead of working it out again:
{definitions_text(manifest_path)}

How to read a question:
- The data holds every regular season and playoff game from 2015-16 to today. Today is
  {today.isoformat()}, so this season is '{season}' and last season is '{last}'.
- Filter seasons with the season column (season BETWEEN '2015-16' AND '2025-26'),
  never with a range of dates.
- When a question doesn't say which season type, include both.
- Player names are stored with their accents, like 'Luka Dončić' and 'Nikola Jokić'.
- When a question asks for the single most (or least), return every row tied for first,
  not only one of them. When it asks for a top N ("which four players"), return N rows.

How the result should look, because it is shown to the person who asked:
- Name what each number belongs to: a player by player_name, a team by its abbreviation,
  a season by its label. Never only an ID.
- A single game is identified by its game_date and both teams' abbreviations (home and
  away), not its game_id.
- A team's record is wins and losses as two numbers, not a win percentage.
- Home and road games are labelled 'home' and 'away'.
- Minutes rounded to 1 decimal.
- Averages rounded to 1 decimal place; a share or percentage of a total as a fraction
  between 0 and 1, rounded to 3 places.
- For a record in a single game or season, include who set it and when (the game_date or
  the season), along with the number.
- Return only the columns that answer the question and say whose and when; no extra IDs.

Reply with the query in one ```sql block and nothing else."""
