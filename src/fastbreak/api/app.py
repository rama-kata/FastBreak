"""The HTTP API the web app calls: ask a question, last night's games, how fresh the data is.

Run it with `uv run fastbreak serve`. The web app on Vercel reaches it through a tunnel,
so when FASTBREAK_API_KEY is set every request except /api/health must carry it in the
X-FastBreak-Key header. The browser never sees the key: the web app's server adds it.
"""

import asyncio
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from collections import deque
from contextlib import closing
from dataclasses import asdict

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from fastbreak.agent.agent import ask
from fastbreak.agent.grounding import number_spans
from fastbreak.agent.llm import LLMError, Ollama

MAX_QUESTION_CHARS = 300
HOURLY_LIMIT = 10  # questions per visitor per hour
DAILY_LIMIT = 150  # questions from everyone per day: about two GPU-hours with thinking

log = logging.getLogger(__name__)

LATEST_GAMES_SQL = """
WITH latest AS (SELECT MAX(game_date) AS d FROM games),
top AS (
    SELECT s.game_id, p.full_name, t.abbreviation, s.pts,
           ROW_NUMBER() OVER (PARTITION BY s.game_id ORDER BY s.pts DESC, p.full_name) AS rn
    FROM player_game_stats s
    JOIN players p USING (player_id)
    JOIN teams t ON t.team_id = s.team_id
    JOIN games g USING (game_id)
    WHERE g.game_date = (SELECT d FROM latest)
)
SELECT g.game_id, g.game_date, g.overtimes,
       a.abbreviation, a.name, g.away_pts,
       h.abbreviation, h.name, g.home_pts,
       top.full_name, top.abbreviation, top.pts
FROM games g
JOIN teams a ON a.team_id = g.away_team_id
JOIN teams h ON h.team_id = g.home_team_id
LEFT JOIN top ON top.game_id = g.game_id AND top.rn = 1
WHERE g.game_date = (SELECT d FROM latest)
ORDER BY g.game_id
"""


class Limits:
    """Questions per visitor per hour and in total per day, so the public site can't keep
    the GPU busy around the clock. Counts live in memory and reset when the API restarts."""

    def __init__(self, hourly, daily, clock=time.monotonic):
        self.hourly, self.daily, self.clock = hourly, daily, clock
        self.by_client = {}
        self.everyone = deque()
        self.lock = threading.Lock()

    def take(self, client):
        """Count one question from `client`, or say why it's refused (None when allowed)."""
        now = self.clock()
        with self.lock:
            while self.everyone and now - self.everyone[0] > 86_400:
                self.everyone.popleft()
            mine = self.by_client.setdefault(client, deque())
            while mine and now - mine[0] > 3600:
                mine.popleft()
            if len(self.everyone) >= self.daily:
                return "FastBreak has answered all the questions it can today. Try again tomorrow."
            if len(mine) >= self.hourly:
                return f"That's {self.hourly} questions this hour. Try again a little later."
            mine.append(now)
            self.everyone.append(now)
            return None


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)


def _readonly(db_path):
    return closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True))


def _sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def result_payload(result, model):
    """What the web app needs from an agent Result. The draft only goes out when it was held back."""
    data = asdict(result)
    data.pop("steps")  # timings and tokens per step: kept in the trace, not sent to browsers
    data["seconds"] = round(result.seconds, 1)
    data["model"] = model
    data["blocked"] = result.error is None and result.answer is None
    if not data["blocked"]:
        data["draft_answer"] = None
    shown = result.answer or data["draft_answer"] or ""
    data["number_spans"] = [
        {"start": a, "end": b, "in_rows": in_rows, "grounded": grounded}
        for a, b, in_rows, grounded in number_spans(shown, result.rows, result.question)
    ]
    return data


def create_app(db_path, make_llm, api_key=None, limits=None):
    """`make_llm()` returns the chat model to answer with; tests pass a fake one.

    The web app's server names the visitor in X-FastBreak-Client (their IP), which only
    counts when the API key is checked, since otherwise anyone could set it."""
    app = FastAPI(title="FastBreak API")
    limits = limits or Limits(HOURLY_LIMIT, DAILY_LIMIT)
    # One GPU box: answer one question at a time and tell anyone else it's busy.
    busy = threading.Lock()

    def check_key(x_fastbreak_key: str | None = Header(default=None)):
        if api_key and not secrets.compare_digest(x_fastbreak_key or "", api_key):
            raise HTTPException(401, "missing or wrong X-FastBreak-Key")

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/status", dependencies=[Depends(check_key)])
    def status():
        with _readonly(db_path) as conn:
            through, games = conn.execute("SELECT MAX(game_date), COUNT(*) FROM games").fetchone()
        return {"data_through": through, "games": games}

    @app.get("/api/games/latest", dependencies=[Depends(check_key)])
    def latest_games():
        with _readonly(db_path) as conn:
            rows = conn.execute(LATEST_GAMES_SQL).fetchall()
        games = [
            {
                "game_id": r[0],
                "overtimes": r[2],
                "away": {"abbreviation": r[3], "name": r[4], "pts": r[5]},
                "home": {"abbreviation": r[6], "name": r[7], "pts": r[8]},
                "top_scorer": None if r[9] is None else {"name": r[9], "team": r[10], "pts": r[11]},
            }
            for r in rows
        ]
        return {"date": rows[0][1] if rows else None, "games": games}

    @app.post("/api/ask", dependencies=[Depends(check_key)])
    async def ask_question(
        body: Question, request: Request, x_fastbreak_client: str | None = Header(default=None)
    ):
        """Answer one question as a stream of server-sent events.

        Events: `sql_written`, `query_failed`, `query_done` while it works, then `result`
        (the answer, or why there isn't one) or `error` (the model couldn't be reached).
        """
        client = (api_key and x_fastbreak_client) or (
            request.client.host if request.client else "?"
        )
        if not busy.acquire(blocking=False):
            raise HTTPException(503, "FastBreak is answering another question. Try again shortly.")
        refused = limits.take(client)
        if refused:
            busy.release()
            raise HTTPException(429, refused)
        loop = asyncio.get_running_loop()
        events = asyncio.Queue()

        def send(event, data):
            loop.call_soon_threadsafe(events.put_nowait, (event, data))

        def work():
            try:
                llm = make_llm()
                result = ask(body.question.strip(), llm, db_path, on_step=send)
                send("result", result_payload(result, llm.name))
            except LLMError as e:
                send("error", {"error": f"the model failed: {e}"})
            except Exception as e:  # the stream must always end with an event
                log.exception("ask failed")
                send("error", {"error": f"something went wrong: {type(e).__name__}"})
            finally:
                busy.release()
                send(None, None)

        # Start now, not when the stream is first read, so the lock is always released
        # even if the caller goes away before reading anything.
        loop.run_in_executor(None, work)

        async def stream():
            yield _sse("started", {"question": body.question.strip()})
            while True:
                event, data = await events.get()
                if event is None:
                    break
                yield _sse(event, data)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def app_from_env():
    """The app `fastbreak serve` runs, configured from environment variables."""
    model = os.environ.get("FASTBREAK_MODEL", "qwen3:14b")
    think = os.environ.get("FASTBREAK_THINK", "1") != "0"
    return create_app(
        db_path=os.environ.get("FASTBREAK_DB", "data/nba.db"),
        make_llm=lambda: Ollama(model, think=think),
        api_key=os.environ.get("FASTBREAK_API_KEY") or None,
        limits=Limits(
            int(os.environ.get("FASTBREAK_HOURLY_LIMIT", HOURLY_LIMIT)),
            int(os.environ.get("FASTBREAK_DAILY_LIMIT", DAILY_LIMIT)),
        ),
    )
