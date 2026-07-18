from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from freddie_pipeline.config import Config

TEST_DB_NAME = "freddie_pipeline_test"


def _db_available() -> bool:
    import psycopg

    try:
        with psycopg.connect(Config.from_env().conninfo(), connect_timeout=3):
            return True
    except psycopg.OperationalError:
        return False


_DB_UP: bool | None = None


def db_up() -> bool:
    global _DB_UP
    if _DB_UP is None:
        _DB_UP = _db_available()
    return _DB_UP


def pytest_collection_modifyitems(config, items):
    if db_up():
        return
    skip = pytest.mark.skip(reason="Postgres not reachable; set FREDDIE_DB_* or start docker")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def test_db_config():
    import psycopg

    base = Config.from_env()
    with psycopg.connect(base.conninfo(), autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        conn.execute(f"CREATE DATABASE {TEST_DB_NAME}")
    yield Config(
        db_host=base.db_host,
        db_port=base.db_port,
        db_user=base.db_user,
        db_password=base.db_password,
        db_name=TEST_DB_NAME,
        sql_dir=REPO_ROOT / "sql",
    )
    with psycopg.connect(base.conninfo(), autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
