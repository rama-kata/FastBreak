import re
import sqlite3
import time
from dataclasses import dataclass

MAX_ROWS = 200
TIMEOUT_SECONDS = 10


class QueryError(Exception):
    """The query was refused, failed, or ran too long. The message goes back to the model."""


@dataclass(frozen=True)
class QueryResult:
    columns: list
    rows: list
    truncated: bool  # more than MAX_ROWS rows; only the first MAX_ROWS are kept


def extract_sql(text):
    """The SQL in a model reply: the last ```sql block, else the whole reply."""
    blocks = re.findall(r"```(?:sql|sqlite)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    sql = (blocks[-1] if blocks else text).strip()
    return sql.rstrip(";").strip()


def run_readonly(db_path, sql, max_rows=MAX_ROWS, timeout=TIMEOUT_SECONDS):
    """Run one query on a read-only connection.

    Read-only twice over: the file is opened with mode=ro, so SQLite can't write it, and
    query_only refuses any statement that would. A progress handler stops a query that
    runs longer than `timeout` seconds, such as an accidental cross join.
    """
    if not sql:
        raise QueryError("the reply had no SQL in it")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only = ON")
        deadline = time.monotonic() + timeout
        conn.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)
        try:
            cursor = conn.execute(sql)
            rows = cursor.fetchmany(max_rows + 1)
        except sqlite3.OperationalError as e:
            if str(e) == "interrupted":
                raise QueryError(f"the query ran longer than {timeout} seconds") from e
            raise QueryError(str(e)) from e
        except sqlite3.Error as e:  # e.g. more than one statement, or a write
            raise QueryError(str(e)) from e
        columns = [d[0] for d in cursor.description or []]
        return QueryResult(columns, [tuple(r) for r in rows[:max_rows]], len(rows) > max_rows)
    finally:
        conn.close()
