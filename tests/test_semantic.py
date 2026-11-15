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
