# Incidents

Every real failure goes here, newest at the top.

Format for each one:

```
## YYYY-MM-DD: short title
- What happened:
- Impact:
- Cause:
- Fix:
- Test that now catches it:
```

## 2026-10-28: a box score with no team stats crashed the nightly run
- What happened: nightly run #35 crashed with `AttributeError: 'NoneType' object has no attribute 'get'`, after loading the game log and before any box score. Found on 2026-10-30 by `fastbreak metrics`, which lists failed runs with their reasons.
- Impact: none lasting. That night's box scores weren't loaded, and the run was recorded as `crashed`. The next morning's nightly re-fetched the last 3 days and loaded them.
- Cause: the PC was off at 09:00, so the timer (`Persistent=true`) ran the job at 19:28 local time, while that evening's games were being played. NBA.com answered for a game in progress with its team stats still `null`, and `nba_api`'s own parser failed on the `None` inside the endpoint call. The fetcher only expected network errors and `ValueError`, so the error went straight past it and stopped the run.
- Fix: the fetcher turns an `AttributeError`, `TypeError` or `KeyError` raised inside an endpoint call into `IncompleteResponse`. It's a `ValueError`, so the box score loop marks the game failed and moves on, without counting it towards "probably blocked". It isn't retried or cached, because the data won't fill in within a minute. The next nightly fetches the game again.
- Test that now catches it: `test_an_incomplete_response_is_not_retried_or_cached` in `tests/test_fetch.py`, `test_box_scores_that_arent_filled_in_yet_dont_stop_the_run` in `tests/test_run.py`.

## 2026-10-20: a game still being played was recorded as failed
- What happened: the first `fastbreak nightly` run under systemd, on 2026-27 opening night, reported "0 games in the game log, 1 failed". BOS @ DET (`0022600001`) was in the first quarter.
- Impact: none on the data. The game was refused, not stored, and marked `failed`. A run late in a game could have stored partial stats until the next morning's refresh corrected them.
- Cause: `LeagueGameLog` lists games while they're being played, with `WL` empty and partial minutes. 0 team minutes made `overtimes` -10, which validation refused.
- Fix: `transform.kept()` skips rows with no result. Checked against every cached season since 2015-16: the only rows with no result were that game's 21.
- Test that now catches it: `test_a_game_still_being_played_is_skipped` in `tests/test_transform.py`.

## 2026-10-19: box score runs stuck on "running", two of them at once
- What happened: `fastbreak status` showed runs #14, #15 and #16 as `running` with no process behind any of them. #15 and #16 had been started 16 minutes apart and were both fetching at the same time until they were killed; #14 had died earlier without a trace.
- Impact: status said work was in progress when nothing was. Two runs at once doubled the request rate on NBA.com, which had already blocked runs #12 and #13. No box score data was lost: each game is recorded as it loads.
- Cause: a run only recorded its end when it finished or gave up after 10 failures in a row. `kill`, Ctrl-C, a crash or a reboot left it `running` forever, and nothing stopped a second run starting on the same database.
- Fix: every run goes through `run.tracked_run()`. It takes a lock on `<db>.lock` so a second run is refused, closes any run a dead process left as `running`, and records `interrupted` or `crashed` when a run stops early. The CLI turns `kill` (SIGTERM) into the same clean stop as Ctrl-C. #14 to #16 were closed by hand in the database.
- Test that now catches it: `test_a_stopped_run_records_that_it_was_interrupted`, `test_a_crashed_run_records_why`, `test_a_second_run_is_refused_while_one_is_going`, `test_a_run_left_running_by_a_dead_process_is_closed_by_the_next_one`, `test_kill_stops_a_run_like_ctrl_c` in `tests/test_run.py`.
