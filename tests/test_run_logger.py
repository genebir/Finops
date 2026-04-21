"""Tests for pipeline_run_log table and run logger sensor helpers."""
from __future__ import annotations

import datetime

import psycopg2
import pytest

from dagster_project.config import load_config
from dagster_project.db_schema import ensure_tables


@pytest.fixture()
def pg_conn():
    cfg = load_config()
    conn = psycopg2.connect(
        host=cfg.postgres.host,
        port=cfg.postgres.port,
        dbname=cfg.postgres.dbname,
        user=cfg.postgres.user,
        password=cfg.postgres.password,
    )
    conn.autocommit = True
    ensure_tables(conn, "pipeline_run_log")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM pipeline_run_log WHERE run_id LIKE 'test_%'")
    conn.close()


def test_pipeline_run_log_insert(pg_conn) -> None:
    now = datetime.datetime.now(datetime.UTC)
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_run_log
              (run_id, asset_key, partition_key, status, started_at, finished_at,
               duration_sec, row_count, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                "test_run_001",
                "gold_marts",
                "2025-01",
                "success",
                now,
                now,
                1.23,
                100,
                None,
            ),
        )
    with pg_conn.cursor() as cur:
        cur.execute("SELECT status, duration_sec FROM pipeline_run_log WHERE run_id = %s", ("test_run_001",))
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "success"
    assert abs(row[1] - 1.23) < 0.01


def test_pipeline_run_log_failure_insert(pg_conn) -> None:
    now = datetime.datetime.now(datetime.UTC)
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_run_log
              (run_id, asset_key, partition_key, status, started_at, finished_at,
               duration_sec, row_count, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                "test_run_002",
                "silver_focus",
                "2025-02",
                "failure",
                now,
                now,
                0.5,
                0,
                "Something went wrong",
            ),
        )
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT status, error_message FROM pipeline_run_log WHERE run_id = %s",
            ("test_run_002",),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "failure"
    assert row[1] == "Something went wrong"


def test_pipeline_run_log_idempotent_schema(pg_conn) -> None:
    # ensure_tables should be idempotent
    ensure_tables(pg_conn, "pipeline_run_log")
    ensure_tables(pg_conn, "pipeline_run_log")
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public' AND tablename='pipeline_run_log'"
        )
        count = cur.fetchone()[0]
    assert count == 1
