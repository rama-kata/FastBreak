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
- [ ] Phase 3: nightly data pipeline
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
```

Then open `notebooks/01_explore.ipynb` in VS Code and pick the `.venv` kernel.

## Project notes

- [DECISIONS.md](DECISIONS.md): one line per decision and why
- [INCIDENTS.md](INCIDENTS.md): real failures and how they were fixed
