# Decisions

One line per decision and why. Newest at the bottom.

## Phase 1: exploring the data (Oct 2026)

Checked against the 2024-25 regular season: 26,306 player rows, 2,460 team rows, 1,230 games.

- One `LeagueGameLog` call gets a whole season, so loading 2015 onwards takes about 45 calls, not thousands of box scores.
- I'm not using Kaggle for v1. `LeagueGameLog` already covers every season I need.
- `GAME_ID` stays text. It has leading zeros (`0022400061`) and turning it into a number would break joins with other endpoints.
- I store the season as `2024-25`, not the API's `SEASON_ID` (`22024`). The first digit of `SEASON_ID` is the season type (2 = regular season, 4 = playoffs), so I keep season type in its own column.
- Player points add up to the team score in all 2,460 team games, so this becomes an automatic check in the pipeline.
- I can't use `MATCHUP` alone to tell home from away. 5 games had both teams listed as away (`@`): the Mexico City game, the two NBA Cup semifinals in Las Vegas, and the two Paris games. I take home and away from `ScoreboardV3`'s `gameCode` (`20250315/BOSBKN` = away BOS, home BKN) and use its `isNeutral` column to mark neutral-site games.
- Team minutes are 240, 265 or 290, which tells me how many overtimes a game had. I keep it for the minutes check.
- `LeagueGameLog` rounds player minutes to whole numbers, but the box score gives `MM:SS` strings. I store minutes as seconds so both sources fit.
- 100 player rows show 0 minutes and 15 of them still have stats. These are players who played under 30 seconds, so I keep them and don't treat 0 minutes as "didn't play".
- Players who didn't play aren't in `LeagueGameLog` at all. The box score lists them with a `comment` (the reason). v1 only stores players who played.
- I don't store the percentage columns. They're empty when a player took no shots (5,362 empty three-point percentages), and I can work them out from makes and attempts.
- I drop `FANTASY_PTS` and `VIDEO_AVAILABLE`. Nothing in v1 needs them.
- 81 players played for more than one team in 2024-25 because of trades, so `team_id` goes on each game row, not on the player.
- I'm using `ScoreboardV3`, not V2. `nba_api` warns that V2 has broken line scores for early 2025-26 games.
- The box score (V3) uses different column names (`points`, `reboundsTotal`, `personId`) from `LeagueGameLog` (`PTS`, `REB`, `PLAYER_ID`). The transform maps both to one schema.
