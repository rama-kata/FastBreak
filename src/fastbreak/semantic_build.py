"""Rebuild the dbt semantic layer after the nightly load, without the live API ever seeing
a half-built one.

dbt builds into a new file next to the old one and writes its manifest to a separate
target directory. Only when every model and test passes are both moved into place, each
with an atomic rename: a question already running keeps reading the old file, and the next
one opens the new. A failed build leaves the last good layer serving. Needs the `semantic`
dependency group.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path("semantic")
SEMANTIC_DB = Path("data/semantic.duckdb")


class BuildFailed(Exception):
    """dbt couldn't build the layer, or one of its tests failed."""


def rebuild(nba_db, semantic_db=SEMANTIC_DB, project=PROJECT, log=print):
    """Build the semantic layer from `nba_db` and swap it in. Returns the new file's path."""
    dbt = Path(sys.executable).parent / "dbt"  # dbt runs in its own process, so nothing it
    if not dbt.exists():  # leaves open (it keeps a DuckDB connection) stays in this one
        raise BuildFailed("dbt isn't installed (uv sync --group semantic)")

    project, semantic_db = Path(project).resolve(), Path(semantic_db).resolve()
    building = semantic_db.with_name(semantic_db.stem + "_building.duckdb")
    target = project / "target-build"
    for leftover in (building, building.with_name(building.name + ".wal")):
        leftover.unlink(missing_ok=True)
    env = os.environ | {
        "FASTBREAK_NBA_DB": str(Path(nba_db).resolve()),
        "FASTBREAK_SEMANTIC_DB": str(building),
    }
    args = ["build", "--profiles-dir", ".", "--target-path", str(target)]
    run = subprocess.run(
        [str(dbt), *args], check=False, cwd=project, env=env, capture_output=True, text=True
    )
    if run.returncode != 0:
        building.unlink(missing_ok=True)
        failures = [ln for ln in run.stdout.splitlines() if "FAIL" in ln or "ERROR" in ln]
        reason = "; ".join(failures[-3:]) or "a model or test failed"
        raise BuildFailed(f"dbt build: {reason}. The last good layer stays in place")
    (project / "target").mkdir(exist_ok=True)
    os.replace(building, semantic_db)
    os.replace(target / "manifest.json", project / "target" / "manifest.json")
    shutil.rmtree(target, ignore_errors=True)
    log(f"semantic layer rebuilt: {semantic_db}")
    return semantic_db
