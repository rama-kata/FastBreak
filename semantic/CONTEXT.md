# FastBreak context contract

What the semantic layer promises to anyone who reads it: people, dashboards, and the
agent. If a definition here changes, the dbt tests and the agent's test set are re-run.

## Where it comes from

- **Source:** `data/nba.db`, loaded by the pipeline every morning at 09:00. dbt attaches
  it read-only and never writes to it.
- **Built into:** `data/semantic.duckdb`, by `dbt build`. Not automated yet: run it after
  the nightly load. Until then the marts are as fresh as the last build.
- **Covers:** every regular season and playoff game from 2015-16 on. Play-In and
  All-Star games are left out by the pipeline.

## Tables to query

Only the marts. The staging models are views into `nba.db` and don't work outside dbt.

| Table | One row per | Use it for |
|---|---|---|
| `fct_player_games` | player per game they played in | Anything about players |
| `fct_team_games` | team per game (each game appears twice) | Records, team scoring, margins |
| `dim_players` | player | Names (stored with accents: Luka Dončić) |
| `dim_teams` | team | Abbreviations and names |

## Definitions

| Term | Definition | Where |
|---|---|---|
| Minutes | seconds / 60.0 | `fct_player_games.minutes` |
| Starter / off the bench | From the box score. **Null** until it loads, so bench queries skip those games instead of miscounting them | `is_starter`, `off_bench` |
| Home / away | As the schedule lists it. Neutral-site games keep a designated home team; `is_neutral` marks them, complete from 2024-25 on | `home_away`, `is_neutral` |
| Win | The team scored more than its opponent | `fct_team_games.won` |
| Record | Wins and losses as two numbers, not a percentage | metrics `wins`, `losses` |
| Double-double | 10 or more in at least two of pts, reb, ast, stl, blk | `is_double_double` |
| Triple-double | 10 or more in at least three of them | `is_triple_double` |
| Per game | Total / games the player appeared in | metrics `*_per_game` |
| Shooting % over many games | Total makes / total attempts, as a fraction between 0 and 1. Never an average of each game's percentage | `field_goal_pct`, `three_point_pct`, `free_throw_pct` |
| Season | Written `2024-25`; `season_type` is `Regular Season` or `Playoffs` | `season`, `season_type` |

## What the tests guarantee

Every `dbt build` checks: unique keys, valid team and player references, allowed values
for `season_type` and `home_away`, one row per player per game, two sides and one winner
per game, no player's game lost in the joins, and player points adding up to the team
score. A failing test stops the build.

## Checked against the test set

Built from these definitions, the marts and metrics return the approved answers for
Westbrook's 42 and Jokić's 19 triple-doubles, Clarkson's 141 bench 20-point games,
LeBron's 27.5 / 27.4 home and away (2017-18), Curry's 30.1 points per game, 2,700
minutes and 0.454 from three (2015-16), and the Spurs' 40-1 home record (2015-16).
