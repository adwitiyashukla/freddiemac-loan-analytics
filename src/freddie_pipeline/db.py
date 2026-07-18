from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg

from .config import Config
from .utils import PipelineError, get_logger

log = get_logger(__name__)


def connect(config: Config) -> psycopg.Connection:
    try:
        return psycopg.connect(config.conninfo())
    except psycopg.OperationalError as exc:
        raise PipelineError(
            f"Could not connect to Postgres ({config.safe_conninfo()}). "
            f"Is the database running? Start it with: "
            f"docker compose -f docker/docker-compose.yml up -d\n  Driver said: {exc}"
        ) from exc


def run_sql_file(conn: psycopg.Connection, path: Path) -> None:
    if not path.is_file():
        raise PipelineError(f"SQL file not found: {path}")
    sql = path.read_text(encoding="utf-8")
    if not sql.strip():
        raise PipelineError(f"SQL file is empty: {path}")
    log.info("Executing %s", path.name)
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def sql_files_in_order(sql_dir: Path) -> list[Path]:
    if not sql_dir.is_dir():
        raise PipelineError(f"SQL directory not found: {sql_dir}")
    files = sorted(sql_dir.glob("*.sql"))
    if not files:
        raise PipelineError(f"No .sql files found in {sql_dir}")
    return files


def fetch_one(conn: psycopg.Connection, query: str, params: tuple = ()) -> tuple[Any, ...]:
    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
    if row is None:
        raise PipelineError(f"Query returned no rows: {query}")
    return row


def fetch_all(
    conn: psycopg.Connection, query: str, params: tuple = ()
) -> list[tuple[Any, ...]]:
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def table_count(conn: psycopg.Connection, table: str) -> int:
    return int(fetch_one(conn, f"SELECT COUNT(*) FROM {table}")[0])
