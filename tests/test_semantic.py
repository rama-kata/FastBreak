"""The semantic-layer query runner. Skipped when DuckDB (the `semantic` group) isn't installed."""

import pytest

duckdb = pytest.importorskip("duckdb")

from fastbreak.agent import semantic
from fastbreak.agent.sql import QueryError


@pytest.fixture
def layer(tmp_path):
    path = tmp_path / "semantic.duckdb"
    conn = duckdb.connect(str(path))
    conn.execute(
        "CREATE TABLE fct_team_games AS SELECT * FROM (VALUES "
        "('0022400061', DATE '2024-11-02', 'BOS', 120), "
        "('0022400062', DATE '2024-11-03', 'NYK', 99)) t(game_id, game_date, team_abbr, points)"
    )
    conn.close()
    return path


def test_dates_come_back_as_text_like_nba_db(layer):
    result = semantic.run_readonly(layer, "SELECT game_date, points FROM fct_team_games ORDER BY 1")
    assert result.rows == [("2024-11-02", 120), ("2024-11-03", 99)]
    assert result.columns == ["game_date", "points"]


def test_rows_are_capped(layer):
    result = semantic.run_readonly(layer, "SELECT * FROM fct_team_games", max_rows=1)
    assert len(result.rows) == 1 and result.truncated


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE x AS SELECT 1",
        "DELETE FROM fct_team_games",
        "COPY fct_team_games TO 'out.csv'",
        "SELECT * FROM read_csv('/etc/passwd')",
        "ATTACH 'other.duckdb' AS other",
    ],
)
def test_writes_and_file_access_are_refused(layer, sql):
    with pytest.raises(QueryError):
        semantic.run_readonly(layer, sql)


def test_a_long_query_is_stopped(layer):
    with pytest.raises(QueryError, match="longer than"):
        semantic.run_readonly(
            layer, "SELECT count(*) FROM range(1000000000) a, range(1000000000) b", timeout=0.5
        )


def test_a_missing_layer_is_a_query_error(tmp_path):
    with pytest.raises(QueryError, match="can't be opened"):
        semantic.run_readonly(tmp_path / "nope.duckdb", "SELECT 1")


def test_values_json_cant_hold_come_back_as_text(layer):
    result = semantic.run_readonly(
        layer, "SELECT INTERVAL 90 MINUTE, TIME '19:30:00', 1.50::DECIMAL(4,2)"
    )
    assert result.rows == [("1:30:00", "19:30:00", 1.5)]


def test_the_season_rule_includes_this_season(tmp_path):
    from datetime import date

    from fastbreak.agent import semantic as s

    db = tmp_path / "semantic.duckdb"
    conn = duckdb.connect(str(db))
    for name in s.MARTS:
        conn.execute(f"CREATE TABLE {name} (id INTEGER)")
    conn.close()
    nodes = {
        f"model.fastbreak.{name}": {
            "name": name,
            "resource_type": "model",
            "description": "",
            "columns": {},
        }
        for name in s.MARTS
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(__import__("json").dumps({"nodes": nodes, "metrics": {}}))
    prompt = s.sql_system_prompt(date(2026, 11, 14), db, manifest)
    assert "season BETWEEN '2015-16' AND '2026-27'" in prompt
    assert "'2025-26'" in prompt  # last season, named as such


def test_a_missing_build_says_how_to_build_it(tmp_path):
    with pytest.raises(semantic.SemanticUnavailable, match="dbt build"):
        semantic.sql_system_prompt(None, tmp_path / "nope.duckdb", tmp_path / "manifest.json")


def test_the_key_lists_each_table_with_its_grain_then_the_definitions_used(tmp_path):
    from fastbreak.agent import semantic as s

    def model(name, description, columns):
        return {
            "name": name,
            "resource_type": "model",
            "description": description,
            "columns": {c: {"description": d} for c, d in columns.items()},
        }

    nodes = {
        "model.fastbreak.fct_player_games": model(
            "fct_player_games",
            "One row per player per game they played in. More detail here.",
            {
                "is_double_double": "10 or more in at least two of pts, reb, ast, stl, blk.",
                "pts": "Points.",  # needs no definition, so it isn't listed
            },
        ),
        "model.fastbreak.fct_games": model("fct_games", "One row per game.", {}),
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(__import__("json").dumps({"nodes": nodes}))
    sql = "SELECT player_name, COUNT(*) FROM fct_player_games WHERE is_double_double AND pts > 20"
    assert s.definitions_used(sql, manifest) == [
        {
            "name": "fct_player_games",
            "label": "Player games",
            "kind": "table",
            "text": "One row per player per game they played in.",
        },
        {
            "name": "is_double_double",
            "label": "Double-double",
            "kind": "column",
            "text": "10 or more in at least two of pts, reb, ast, stl, blk.",
        },
    ]
