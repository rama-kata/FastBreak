import pytest

from fastbreak.db import connect, init_db


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    conn = connect(path)
    init_db(conn)
    conn.execute("INSERT INTO teams VALUES (1610612744, 'GSW', 'Golden State Warriors')")
    conn.execute("INSERT INTO teams VALUES (1610612747, 'LAL', 'Los Angeles Lakers')")
    conn.commit()
    conn.close()
    return path
