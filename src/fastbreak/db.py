import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).parent / "schema.sql"


def init_db(conn):
    """Create every table in schema.sql. Safe to run on an existing database."""
    conn.executescript(SCHEMA.read_text())


def connect(path):
    """Open the SQLite database at path, with foreign keys and WAL mode on."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn
