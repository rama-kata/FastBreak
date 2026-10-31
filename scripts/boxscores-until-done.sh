#!/usr/bin/env bash
# Rerun `fastbreak boxscores` until no box scores are left, with a cooldown between runs.
# Cooldown: 15 min, doubling (max 2 h) while runs make no progress, back to 15 min after progress.
# Stops by itself when nothing is pending, or after 8 runs in a row with no progress.
set -u
cd /home/kuoch/FastBreak
LOG=data/boxscores.log
MIN=900 MAX=7200 wait=$MIN stuck=0

pending() {
  uv run python -c "from fastbreak.db import connect; from fastbreak.pipeline.run import pending_boxscores; print(len(pending_boxscores(connect('data/nba.db'))))"
}
say() { echo "[loop $(date '+%F %T')] $*" >> "$LOG"; }

while :; do
  before=$(pending)
  if [ "$before" -eq 0 ]; then say "nothing left to download, done"; break; fi
  say "starting run, $before games pending"
  uv run fastbreak boxscores >> "$LOG" 2>&1
  after=$(pending)
  [ "$after" -eq 0 ] && { say "nothing left to download, done"; break; }
  if [ "$after" -lt "$before" ]; then
    wait=$MIN stuck=0
  else
    stuck=$((stuck + 1))
    [ "$stuck" -ge 8 ] && { say "no progress in 8 runs in a row, giving up"; break; }
    [ "$stuck" -gt 1 ] && wait=$(( wait * 2 > MAX ? MAX : wait * 2 ))
  fi
  say "run ended, $after pending; waiting $((wait / 60)) min before the next one"
  sleep "$wait"
done
