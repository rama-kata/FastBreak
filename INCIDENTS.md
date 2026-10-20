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
