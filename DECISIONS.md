# Decisions

One line per decision and why. Newest at the bottom.

## Phase 1: exploring the data (Oct 10 2026)

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

## Phase 2: the database (Oct 14 2026)

- Who started isn't in `LeagueGameLog`, only in the box score (the 5 players per team with a `position`). I load seasons from `LeagueGameLog` first, then fill in `starter` from box scores. That's about 14,000 calls, so it runs overnight and has to resume after failures.
- The foreign key test first inserts a valid row, then checks the error message says FOREIGN KEY. My first version passed for the wrong reason: the row was missing required columns, which raised the same error type.

## Phase 3: the pipeline (Oct 16 2026)

- `nba_api` doesn't raise an error for a bad HTTP status. A blocked or failed request comes back as an error page, which only fails when it's parsed as JSON. So the fetcher retries `ValueError` as well as network errors, and nothing else, so real bugs crash straight away.
- v1 skips Play-In and All-Star games. `LeagueGameLog` includes them, and the first digit of `SEASON_ID` says which (5 = Play-In, 3 = All-Star), so `transform.kept()` filters on it.
- Transform functions return lists of rows, never dicts keyed by ID. A dict keyed by `player_id` keeps one game per player and silently drops the rest (569 rows instead of 26,306). Duplicates are the database's job, through primary keys.
- Neutral-site games get their home team from `ScoreboardV3`'s `gameCode`, fetched only for those games (5 a season). `transform.games()` raises an error if one is missing, instead of guessing.
- Reloading the game log keeps `starter`: the upsert uses `COALESCE(excluded.starter, player_game_stats.starter)`, because the game log always sends it empty.
- Loaded the full 2024-25 regular season: 1,230 games, 26,306 player rows, 569 players, 5 neutral-site games, 56 single-overtime and 4 double-overtime games. All match the Phase 1 exploration.
- Each game is validated on its own when a season loads. A broken game is marked `failed` in `game_ingest` with the reason, and the rest of the season still loads.
- The box score step picks up every game whose game log is done and whose box score isn't, newest first. That query is what makes it resumable: a crash or restart continues where it stopped and never refetches a finished game.
- A game that fails 3 times is left for me to look at. After 10 failed calls in a row the run stops, because that almost always means NBA.com has blocked us.
- Once the box score has loaded, a game log reload keeps its exact seconds as well as `starter`. My first version of the upsert overwrote exact seconds with rounded minutes on every reload.
- `is_neutral` is only complete from 2024-25 on. Earlier neutral-site games, including the 2019-20 Orlando bubble, list a designated home team with "vs.", so they look like normal home games. Fixing it would mean one `ScoreboardV3` call per game date (about 1,800 calls); v1 doesn't need it.
- Loaded every season from 2015-16 in 100 seconds: 14,128 games, 300,879 player rows, 1,556 players, none failed. 2019-20 (1,059 games) and 2020-21 (1,080) are short because of COVID.
- Only one pipeline run at a time per database, using a `flock` on `<db>.lock`. The OS releases a `flock` when the process dies, even on `kill -9`, so a crash can never leave the lock stuck. It also means whoever holds the lock knows any run still marked `running` is dead and can close it.
- A run now stops after 2 failed games in a row, not 10 (`--max-failures-in-row` changes it). Each failed game has already been tried 5 times, so 10 in a row meant up to 50 requests and about 30 minutes of hitting NBA.com while it was blocking us. On 2026-10-19 three runs (#12, #13, #18) ended that way. The restart loop waits 15 minutes or more after a run stops, so stopping early costs nothing.
- The nightly run re-fetches the whole current season's game log, not just yesterday's games. Stat corrections come from the game log (its upsert rewrites every stat), and a correction can land on any game, so a full refresh is the only way to be sure. It's 4 calls.
- Box scores only carry `starter` and exact seconds, so the nightly run re-fetches them for the last 3 days only, which is when minutes get corrected. Older missing box scores stay with `fastbreak boxscores`, so a nightly run stays a few dozen calls even during a backfill.
- A re-check that fails never marks an already loaded box score as `failed`. Its data is still good; only the check for a correction didn't get through.
- The nightly run is scheduled with a systemd user timer at 09:00 local time, with `Persistent=true` so a morning the laptop was off still gets a run when it's back on. `journalctl` keeps each run's output.
