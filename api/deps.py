"""Shared FastAPI dependencies — PostgreSQL connections and helpers."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

import psycopg2
import psycopg2.extensions

_PG_DSN = (
    f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
    f"port={os.getenv('POSTGRES_PORT', '5432')} "
    f"dbname={os.getenv('POSTGRES_DBNAME', 'finops')} "
    f"user={os.getenv('POSTGRES_USER', 'finops_app')} "
    f"password={os.getenv('POSTGRES_PASSWORD', 'finops_secret_2026')}"
)


@contextmanager
def db_read() -> Generator[psycopg2.extensions.connection, None, None]:
    """Short-lived read connection per request."""
    conn = psycopg2.connect(_PG_DSN)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def db_write() -> Generator[psycopg2.extensions.connection, None, None]:
    """Short-lived write connection."""
    conn = psycopg2.connect(_PG_DSN)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()


def tables(conn: psycopg2.extensions.connection) -> set[str]:
    """Set of table names in the public schema."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        return {r[0] for r in cur.fetchall()}


def columns(conn: psycopg2.extensions.connection, table: str) -> set[str]:
    """Set of column names for a given table."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s",
            [table],
        )
        return {r[0] for r in cur.fetchall()}


def f(v: Any) -> float:
    """Safely convert a DB value (Decimal/None/int/float) to float."""
    if v is None:
        return 0.0
    return float(Decimal(str(v)))
