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
- [x] Phase 4: test questions with correct answers ([questions](evals/questions.toml))
- [x] Phase 5: first agent ([results](#results-so-far), [decisions](DECISIONS.md))
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

## Results so far

Scored on the 50 approved test questions: a question counts only when the
agent's query returns the right rows. All runs use `qwen3:14b` on Ollama, on a
home PC with an RTX 3060 and an RTX 2070 Super, temperature 0.

| Run | Thinking off | Thinking on | Routed |
|---|---|---|---|
| Baseline: schema and conventions in the prompt | 20/50 (40%) | | |
| Rules for how a result should look | 31/50 (62%) | 40/50 (80%)* | |
| Two ambiguous questions reworded, clearer rules | 33/50 (66%) | 44/50 (88%)* | |
| Context and reply-length fix | 35/50 (70%) | **44/50 (88%)** | |
| Same, re-run with traces (latest) | **36/50 (72%)** | | **40/50 (80%)** |
| Typical / slow answer (latest) | 5.7 s / 26 s | 55 s / 204 s | 11 s / 136 s |
| Model time per correct answer | 13 s | 79 s | 48 s |

\* Measured with a bug: Ollama's default 4,096-token context, which long
reasoning overflowed, silently dropping the start of the prompt. The re-run
after the fix scored the same 44/50, with no reply cut off, though 3 questions
went each way, which is normal run-to-run variation on 50 questions.

What these numbers say, and what they don't:

- **50 questions is a small test.** The latest 36/50 means the true accuracy
  is somewhere between 58% and 82% (95% range), so I compare runs question by
  question on the same 50, not on the headline number.
- **Thinking more than doubles accuracy on hard questions** (5/15 to 11/15)
  for about 9 times the time, while simple questions get 30/35 in about 6
  seconds without it and 33/35 with it. That's the case for routing: fast for
  simple questions, thinking for hard ones.
- **Routing lands in between, as it should.** A quick thinking-off call labels
  each question first. Routed, the agent gets 40/50 for 48 s of model time per
  correct answer: 4 more right than thinking off, 4 fewer than thinking on, at
  about 60% of thinking on's time. The router plays safe: it sent 1 of the 15
  hard questions the fast way (and that one was still right), but 11 of the 35
  simple ones to thinking. Hard answers asked with `fastbreak ask --route` go
  into a review queue for a person to check (`fastbreak review`).
- **Writing the SQL is where the time goes.** With thinking off, a question's
  steps take (p50 / p95): writing the SQL 4.0 s / 18.6 s, running it 0.01 s /
  0.2 s, writing the answer 1.3 s / 2.2 s, and the grounding check under a
  millisecond (`fastbreak metrics`).
- **The grounding check stops invented numbers, not wrong queries.** No reply
  goes out with a number that isn't in the result, but a reply that faithfully
  reports a wrong query's rows passes the check. Only the test set catches those.
- **A much smaller model didn't work.** OLMoE-1B-7B (about 1B parameters used
  per token) scored 1/50: it queried columns that don't exist and answered
  different questions. A small model for simple questions would have to be
  fine-tuned on this schema.
- **Some misses are format, not facts.** Several wrong answers have the right
  numbers in another form, such as a team ID instead of its abbreviation. The
  scorer counts them as wrong.
- **Who checked the test answers:** I checked 12 against outside sources
  myself; 38 were approved on Claude Code's source checks, each recorded with
  its link in `evals/questions.toml`.

Every run is saved in `evals/results/`, one line per question with the SQL,
rows and answer, so any number here can be traced back to the queries behind it.

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
returns the same rows (any column order, extra columns allowed, text compared
ignoring case).

```bash
uv run fastbreak questions show luka-73   # one question, its SQL and answer
uv run fastbreak questions check          # every SQL still runs and matches its answer
uv run fastbreak questions freeze         # save answers for new questions
```

A question starts as `status = "draft"`. Check its answer (Basketball-Reference
is the easiest source), write in `notes` how you checked it, then set
`status = "approved"`. Only approved questions count towards the score.

Questions about this season set `frozen = false`. Nothing is saved for them:
the scorer runs their SQL at scoring time, because the answer changes with
every nightly load.

**Asking the agent**

It needs [Ollama](https://ollama.com) running with the model pulled
(`ollama pull qwen3:14b`).

```bash
uv run fastbreak ask "Who has the most triple-doubles since 2015?"   # SQL, rows, answer
uv run fastbreak ask --think "..."                                   # with the model's reasoning on
uv run fastbreak eval                                                # score every approved question
uv run fastbreak eval --think --id luka-73                           # one question, thinking on
```

The agent writes one SQL query, runs it on a read-only connection (10 second
limit, 200 rows), retries once if the query fails, then writes the answer from
the rows. The answer is held back if a number in it isn't in the rows.

**Routing and review**

```bash
uv run fastbreak ask --route "..."         # simple questions fast, hard ones with thinking
uv run fastbreak eval --route              # score the routed agent; shows how the router did
uv run fastbreak review                    # hard answers waiting for a person to check
uv run fastbreak review 52                 # one of them: question, SQL, rows and answer
uv run fastbreak review 52 right --note "matches Basketball-Reference"
uv run fastbreak review 52 --as-question   # a draft entry for evals/questions.toml
```

A review happens after the answer has gone out: nothing waits on a person. A
reviewed answer with a checked result is a ready-made new test question.

**Traces and metrics**

Every question asked with `fastbreak ask` or scored by `fastbreak eval` is saved
in `data/traces.db`, one trace per question with a span for each step: writing
the SQL, running it, writing the answer, and the grounding check.

```bash
uv run fastbreak metrics                 # latency per step, cost per correct answer, pipeline failures
uv run fastbreak metrics --source eval   # latency from eval runs only
sqlite3 data/traces.db "SELECT question, seconds, error FROM traces ORDER BY trace_id DESC LIMIT 5"
```

The models run locally, so cost per correct answer is measured in model time
and output tokens, not dollars. It's worked out from the saved runs in
`evals/results/`, so runs from before traces existed count too.

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

**Push and open a PR**

Work happens on a branch, never straight on `main`.

```bash
git checkout -b feat/<name>             # start a branch for the work
git push -u origin feat/<name>          # first push of the branch; after that, plain `git push`
gh pr create --base main --fill         # open the PR, titled from the commit message
gh pr view --web                        # look at it on GitHub
gh pr merge --merge                     # merge it once it's reviewed
git checkout main && git pull           # back on main, up to date
```

Never force-push to `main`, and never commit `data/` or `.env`.

## Project notes

- [DECISIONS.md](DECISIONS.md): one line per decision and why
- [INCIDENTS.md](INCIDENTS.md): real failures and how they were fixed
