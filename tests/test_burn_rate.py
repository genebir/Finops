"""Tests for Phase 14 — burn_rate asset and API endpoint."""
from __future__ import annotations

import datetime

import psycopg2
import pytest
from fastapi.testclient import TestClient

from api.main import app
from dagster_project.config import load_config
from dagster_project.db_schema import ensure_tables


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
    ensure_tables(conn, "dim_burn_rate")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dim_burn_rate WHERE team LIKE 'test_%'")
    conn.close()


def test_dim_burn_rate_table_created(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_burn_rate'"
        )
        assert cur.fetchone() is not None


def test_dim_burn_rate_insert_read(pg_conn) -> None:
    now = datetime.datetime.now(datetime.UTC)
    month = "2026-04"
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dim_burn_rate
              (billing_month, team, env, days_elapsed, days_in_month,
               mtd_cost, daily_avg, projected_eom, budget_amount,
               projected_utilization, status, refreshed_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (month, "test_team", "prod", 15, 30,
             5000.0, 333.33, 9999.9, 8000.0, 124.9, "critical", now),
        )
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT status, projected_eom FROM dim_burn_rate WHERE team='test_team'",
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "critical"
    assert abs(row[1] - 9999.9) < 0.1


def test_api_burn_rate_returns_200(client: TestClient) -> None:
    r = client.get("/api/burn-rate")
    assert r.status_code == 200


def test_api_burn_rate_shape(client: TestClient) -> None:
    r = client.get("/api/burn-rate")
    body = r.json()
    assert "items" in body
    assert "summary" in body
    assert "billing_month" in body


def test_api_burn_rate_summary_fields(client: TestClient) -> None:
    body = client.get("/api/burn-rate").json()
    s = body["summary"]
    assert "total_mtd" in s
    assert "total_projected_eom" in s
    assert "critical_count" in s


def test_api_burn_rate_with_month_param(client: TestClient) -> None:
    r = client.get("/api/burn-rate?billing_month=2025-01")
    assert r.status_code == 200
    assert r.json()["billing_month"] == "2025-01"


def test_definitions_has_burn_rate_asset() -> None:
    from dagster_project.definitions import defs
    asset_keys = [str(a.key) for a in defs.assets]  # type: ignore[union-attr]
    assert any("burn_rate" in k for k in asset_keys)


def test_definitions_has_schedules() -> None:
    from dagster_project.definitions import defs
    assert defs.schedules is not None
    schedule_names = [s.name for s in defs.schedules]
    assert "monthly_burn_rate_schedule" in schedule_names
    assert "daily_data_quality_schedule" in schedule_names
