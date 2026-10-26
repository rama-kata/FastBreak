import json
import threading

import pytest
from fastapi.testclient import TestClient

from fastbreak.api.app import MAX_QUESTION_CHARS, create_app
from fastbreak.db import connect, init_db
from tests.test_agent import FakeLLM, sql_reply

GSW, PHX, DEN, NOP = 1610612744, 1610612756, 1610612743, 1610612740


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    conn = connect(path)
    init_db(conn)
    conn.executemany(
        "INSERT INTO teams VALUES (?, ?, ?)",
        [
            (GSW, "GSW", "Golden State Warriors"),
            (PHX, "PHX", "Phoenix Suns"),
            (DEN, "DEN", "Denver Nuggets"),
            (NOP, "NOP", "New Orleans Pelicans"),
        ],
    )
    conn.executemany(
        "INSERT INTO players VALUES (?, ?)",
        [(1, "Devin Booker"), (2, "Stephen Curry"), (3, "Jamal Murray")],
    )
    games = [
        ("0022600001", "2026-10-23", PHX, GSW, 100, 99, 0),  # the night before: left out
        ("0022600010", "2026-10-24", PHX, GSW, 131, 122, 0),
        ("0022600011", "2026-10-24", DEN, NOP, 141, 135, 1),
    ]
    for game_id, day, home, away, home_pts, away_pts, ot in games:
        conn.execute(
            "INSERT INTO games (game_id, season, season_type, game_date, home_team_id,"
            " away_team_id, home_pts, away_pts, overtimes)"
            " VALUES (?, '2026-27', 'Regular Season', ?, ?, ?, ?, ?, ?)",
            (game_id, day, home, away, home_pts, away_pts, ot),
        )
    zeros = (0,) * 14  # fgm through pf
    for game_id, player_id, team_id, pts in [
        ("0022600010", 1, PHX, 43),
        ("0022600010", 2, GSW, 30),
        ("0022600011", 3, DEN, 42),
    ]:
        conn.execute(
            "INSERT INTO player_game_stats VALUES (?, ?, ?, 1, 2400" + ", ?" * 14 + ", ?, 0)",
            (game_id, player_id, team_id, *zeros, pts),
        )
    conn.commit()
    conn.close()
    return path


def client_for(db_path, *replies, api_key=None):
    return TestClient(create_app(db_path, lambda: FakeLLM(*replies), api_key=api_key))


def events(response):
    """The (event, data) pairs in a server-sent event stream."""
    out = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_status_says_how_fresh_the_data_is(db_path):
    assert client_for(db_path).get("/api/status").json() == {
        "data_through": "2026-10-24",
        "games": 3,
    }


def test_latest_games_are_the_last_night_with_games_and_its_top_scorers(db_path):
    body = client_for(db_path).get("/api/games/latest").json()
    assert body["date"] == "2026-10-24"
    assert [g["game_id"] for g in body["games"]] == ["0022600010", "0022600011"]
    suns, nuggets = body["games"]
    assert suns["home"] == {"abbreviation": "PHX", "name": "Phoenix Suns", "pts": 131}
    assert suns["away"]["pts"] == 122
    assert suns["top_scorer"] == {"name": "Devin Booker", "team": "PHX", "pts": 43}
    assert nuggets["overtimes"] == 1


def test_the_api_key_is_required_when_set_but_not_for_health(db_path):
    client = client_for(db_path, api_key="s3cret")
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/status").status_code == 401
    assert client.get("/api/status", headers={"X-FastBreak-Key": "wrong"}).status_code == 401
    assert client.get("/api/status", headers={"X-FastBreak-Key": "s3cret"}).status_code == 200


def test_ask_streams_each_step_then_the_checked_answer(db_path):
    client = client_for(
        db_path,
        sql_reply("SELECT full_name, 43 AS pts FROM players WHERE player_id = 1"),
        "Devin Booker scored 43.",
    )
    response = client.post("/api/ask", json={"question": "Who scored the most last night?"})
    assert response.headers["content-type"].startswith("text/event-stream")
    got = events(response)
    assert [e for e, _ in got] == ["started", "sql_written", "query_done", "result"]
    result = got[-1][1]
    assert result["answer"] == "Devin Booker scored 43."
    assert result["blocked"] is False
    assert result["draft_answer"] is None
    assert result["rows"] == [["Devin Booker", 43]]
    assert result["model"] == "fake"
    assert result["number_spans"] == [{"start": 20, "end": 22, "in_rows": True, "grounded": True}]
    assert "calls" not in result


def test_a_held_back_answer_comes_with_its_draft_and_the_numbers_not_in_the_rows(db_path):
    client = client_for(db_path, sql_reply("SELECT 41 AS wins"), "The Warriors went 82 and 9.")
    result = events(client.post("/api/ask", json={"question": "Warriors record?"}))[-1][1]
    assert result["blocked"] is True
    assert result["answer"] is None
    assert result["draft_answer"] == "The Warriors went 82 and 9."
    assert result["ungrounded"] == [82.0, 9.0]
    assert [s["in_rows"] for s in result["number_spans"]] == [False, False]


def test_numbers_from_the_question_are_allowed_but_not_marked_as_from_the_rows(db_path):
    client = client_for(db_path, sql_reply("SELECT 23 AS games"), "Harden had 23 50-point games.")
    result = events(client.post("/api/ask", json={"question": "Most 50-point games?"}))[-1][1]
    assert result["blocked"] is False
    spans = [(s["in_rows"], s["grounded"]) for s in result["number_spans"]]
    assert spans == [(True, True), (False, True)]


def test_a_failed_query_is_reported_and_retried(db_path):
    client = client_for(
        db_path, sql_reply("SELECT nope FROM players"), sql_reply("SELECT 1 AS one"), "It is 1."
    )
    got = events(client.post("/api/ask", json={"question": "One?"}))
    assert [e for e, _ in got] == [
        "started",
        "sql_written",
        "query_failed",
        "sql_written",
        "query_done",
        "result",
    ]
    assert got[2][1]["retrying"] is True


def test_one_question_at_a_time(db_path):
    working, release = threading.Event(), threading.Event()

    class SlowLLM(FakeLLM):
        def chat(self, messages):
            working.set()
            release.wait(5)
            return super().chat(messages)

    app = create_app(db_path, lambda: SlowLLM(sql_reply("SELECT 1 AS one"), "It is 1."))
    first = {}
    thread = threading.Thread(
        target=lambda: first.update(r=TestClient(app).post("/api/ask", json={"question": "a"}))
    )
    thread.start()
    try:
        assert working.wait(5)
        second = TestClient(app).post("/api/ask", json={"question": "b"})
        assert second.status_code == 503
    finally:
        release.set()
        thread.join(5)
    assert events(first["r"])[-1][0] == "result"


def test_questions_have_a_length_limit(db_path):
    client = client_for(db_path)
    assert (
        client.post("/api/ask", json={"question": "x" * (MAX_QUESTION_CHARS + 1)}).status_code
        == 422
    )
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
