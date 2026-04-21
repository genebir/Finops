"""Tests for Phase 13 — data quality asset and API endpoints."""
from __future__ import annotations

import datetime

import psycopg2
import pytest
from fastapi.testclient import TestClient

from api.main import app
from dagster_project.config import load_config
from dagster_project.db_schema import ensure_tables


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


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
    ensure_tables(conn, "dim_data_quality")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dim_data_quality WHERE table_name = 'test_table'")
    conn.close()


# ── DB-level tests ─────────────────────────────────────────────────────────────

def test_dim_data_quality_table_created(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_data_quality'"
        )
        assert cur.fetchone() is not None


def test_dim_data_quality_insert_and_read(pg_conn) -> None:
    now = datetime.datetime.now(datetime.UTC)
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dim_data_quality
              (checked_at, table_name, column_name, check_type,
               row_count, failed_count, null_ratio, passed, detail)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (now, "test_table", "col_a", "min_rows", 100, 0, None, True, "row_count=100"),
        )
    with pg_conn.cursor() as cur:
        cur.execute("SELECT passed, detail FROM dim_data_quality WHERE table_name='test_table'")
        row = cur.fetchone()
    assert row is not None
    assert row[0] is True
    assert "row_count=100" in row[1]


def test_dim_data_quality_idempotent_schema(pg_conn) -> None:
    ensure_tables(pg_conn, "dim_data_quality")
    ensure_tables(pg_conn, "dim_data_quality")
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public' AND tablename='dim_data_quality'"
        )
        assert cur.fetchone()[0] == 1


# ── API tests ──────────────────────────────────────────────────────────────────

def test_api_data_quality_returns_200(client: TestClient) -> None:
    r = client.get("/api/data-quality")
    assert r.status_code == 200


def test_api_data_quality_shape(client: TestClient) -> None:
    r = client.get("/api/data-quality")
    body = r.json()
    assert "checks" in body
    assert "summary" in body
    assert "total" in body["summary"]
    assert "passed" in body["summary"]
    assert "failed" in body["summary"]
    assert isinstance(body["checks"], list)


def test_api_data_quality_summary_consistent(client: TestClient) -> None:
    body = client.get("/api/data-quality").json()
    s = body["summary"]
    assert s["passed"] + s["failed"] == s["total"]


def test_api_export_fact_daily_cost(client: TestClient) -> None:
    r = client.get("/api/export/fact_daily_cost")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.splitlines()
    assert len(lines) >= 1
    assert "charge_date" in lines[0] or "resource_id" in lines[0]


def test_api_export_anomaly_scores(client: TestClient) -> None:
    r = client.get("/api/export/anomaly_scores")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]


def test_api_export_unknown_table_returns_404(client: TestClient) -> None:
    r = client.get("/api/export/does_not_exist")
    assert r.status_code == 404


def test_api_export_content_disposition(client: TestClient) -> None:
    r = client.get("/api/export/dim_fx_rates")
    assert r.status_code == 200
    assert "dim_fx_rates.csv" in r.headers.get("content-disposition", "")
