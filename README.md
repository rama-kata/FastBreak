# FastBreak

An NBA stats assistant that shows its work. Ask a question in plain English,
like "Who has the most 20-point games off the bench since 2015?", and get an
answer backed by a real query on data that updates every night. Every number
in an answer comes from a query result you can see.

## Status

Early build. Nothing here is live yet.

- [x] Phase 0: project setup
- [x] Phase 1: data exploration ([notebook](notebooks/01_explore.ipynb), [decisions](DECISIONS.md))
- [x] Phase 2: database schema ([schema](src/fastbreak/schema.sql))
- [x] Phase 3: nightly data pipeline
- [ ] Phase 4: test questions with correct answers
- [ ] Phase 5: first agent
- [ ] Phase 6: traces and metrics
- [ ] Phase 7: API and web app

## Goals

- **Answers you can check.** Each answer shows the SQL it ran and the rows it
  came from. If a number in the reply isn't in the results, the reply doesn't
  go out.
- **A pipeline that survives real failures.** Box scores load every night,
  resume where they left off after a crash, and safely re-process games when
  the NBA corrects stats the next day.
- **Measured, not claimed.** A hand-written test set of questions with correct
  answers, scored by whether the agent's query returns the right rows.
- **Cheap where it can be.** Simple questions go to a small local model, hard
  ones to a larger model, with a daily budget enforced in code.

## What I'll measure

- Query accuracy on the test set, before and after each change
- p50 / p95 latency for each step
- Cost per correct answer, not per model call
- Failure rate for each pipeline step

## Scope for version 1

- Regular season and playoffs, 2015-16 to today
- Box scores and player game logs

**Not in version 1:** play-by-play, shot charts, clutch stats, contracts,
injuries or trade rumours.

## Data

Stats come from NBA.com through the [`nba_api`](https://github.com/swar/nba_api)
library, cached locally and requested gently. One `LeagueGameLog` call returns a
whole season, so loading every season since 2015-16 takes about 45 calls.

What exploring the 2024-25 season showed (details in the
[notebook](notebooks/01_explore.ipynb)):

- Player points add up to the team score in all 2,460 team games, so this
  becomes an automatic check in the pipeline.
- `MATCHUP` can't always tell home from away: 5 games were played at neutral
  sites (Mexico City, the NBA Cup semifinals in Las Vegas, and Paris).
- 81 players played for more than one team in a season, so a player's team is
  stored on each game, not on the player.

This is a non-commercial project, and no raw data is stored in this repo.

## Running it

```bash
uv sync
uv run fastbreak load-seasons --from 2015-16   # game logs for every season (~2 minutes)
uv run fastbreak boxscores --limit 500         # starters and exact minutes, newest games first
uv run fastbreak status                        # games done, pending and failed per step
```

The box score step makes about 14,000 calls, roughly 4 hours. It can be stopped
and restarted at any time: it carries on from the games that aren't done yet.

**Every night**

```bash
uv run fastbreak nightly             # this season's new games and corrections
```

It re-fetches the current season's game log, which brings new games and any
corrected stats, then the box scores from the last 3 days (`--days` changes it).
Older missing box scores are left to `fastbreak boxscores`. Only one run can
write to the database at a time, so while a backfill is running it is refused
and runs again the next morning.

To run it every morning at 09:00 with a systemd user timer:

```bash
cp deploy/systemd/fastbreak-nightly.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now fastbreak-nightly.timer
systemctl --user list-timers fastbreak-nightly.timer   # when it runs next
journalctl --user -u fastbreak-nightly                 # what happened last time
```

**The test set**

The questions the agent is scored on live in `evals/questions.toml`, each with
the SQL that answers it. The answer that SQL returns is saved in
`evals/answers/<id>.json`, and an agent's query counts as correct when it
returns the same rows (any column order, extra columns allowed).

```bash
uv run fastbreak questions show luka-73   # one question, its SQL and answer
uv run fastbreak questions check          # every SQL still runs and matches its answer
uv run fastbreak questions freeze         # save answers for new questions
```

A question starts as `status = "draft"`. Check its answer (Basketball-Reference
is the easiest source), write in `notes` how you checked it, then set
`status = "approved"`. Only approved questions count towards the score.

To explore the data, open `notebooks/01_explore.ipynb` in VS Code and pick the
`.venv` kernel.

## Development

Run everything from the repo root.

**Before every commit**

```bash
uv run ruff check --fix src tests    # lint, and fix what it can
uv run ruff format src tests         # consistent formatting
uv run pytest -q                     # all tests pass
git diff                             # read what you're about to commit
```

**Dependencies**

```bash
uv add <package>         # a library the project needs
uv add --dev <package>   # a tool only for development (tests, linting)
uv sync                  # after pulling, or if .venv acts strange
```

Always go through `uv`, never `pip install`, so `uv.lock` stays the single
source of truth.

**Tests in more detail**

```bash
uv run pytest -v                           # each test by name
uv run pytest tests/test_db.py -k reload   # one test
uv run pytest -x                           # stop at the first failure
uv run pytest --lf                         # rerun only what failed last time
```

**Looking inside the database** (once `data/nba.db` exists)

```bash
sqlite3 data/nba.db ".tables"
sqlite3 data/nba.db ".schema games"
sqlite3 -header -column data/nba.db "SELECT * FROM game_ingest WHERE status = 'failed' LIMIT 10"
sqlite3 -header -column data/nba.db "SELECT season, COUNT(*) FROM games GROUP BY season"
```

**Git**

```bash
git status                 # first thing every session: anything unexpected?
git restore <file>         # throw away uncommitted changes to a file
git commit --amend         # fix the last commit, only if it isn't pushed yet
```

Never force-push to `main`, and never commit `data/` or `.env`.

## Project notes

- [DECISIONS.md](DECISIONS.md): one line per decision and why
- [INCIDENTS.md](INCIDENTS.md): real failures and how they were fixed
