"""Tests for Phase 19 — cost trend asset and API endpoints."""
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
    ensure_tables(conn, "dim_cost_trend")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dim_cost_trend WHERE team = 'test_trend_team'")
    conn.close()


def _insert_trend(conn, month: str, team: str, cost: float, provider: str = "aws") -> None:
    now = datetime.datetime.now(datetime.UTC)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dim_cost_trend
              (billing_month, provider, team, env, service_name,
               total_cost, resource_count, anomaly_count, computed_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (month, provider, team, "prod", "EC2", cost, 10, 0, now),
        )


def test_cost_trend_table_created(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_cost_trend'"
        )
        assert cur.fetchone() is not None


def test_cost_trend_insert_read(pg_conn) -> None:
    _insert_trend(pg_conn, "2026-01", "test_trend_team", 1000.0)
    with pg_conn.cursor() as cur:
        cur.execute("SELECT total_cost FROM dim_cost_trend WHERE team='test_trend_team' AND billing_month='2026-01'")
        row = cur.fetchone()
    assert row is not None
    assert abs(row[0] - 1000.0) < 0.1


def test_api_cost_trend_returns_200(client: TestClient) -> None:
    r = client.get("/api/cost-trend")
    assert r.status_code == 200


def test_api_cost_trend_shape(client: TestClient) -> None:
    body = client.get("/api/cost-trend").json()
    assert "series" in body
    assert "months" in body
    assert "summary" in body
    assert isinstance(body["series"], list)


def test_api_cost_trend_with_filters(client: TestClient) -> None:
    r = client.get("/api/cost-trend?provider=aws&team=platform")
    assert r.status_code == 200


def test_api_cost_trend_months_param(client: TestClient) -> None:
    r = client.get("/api/cost-trend?months=3")
    assert r.status_code == 200
    body = r.json()
    assert len(body["series"]) <= 3


def test_api_cost_trend_series_chronological(client: TestClient) -> None:
    body = client.get("/api/cost-trend").json()
    months = body["months"]
    assert months == sorted(months)


def test_api_cost_trend_compare_returns_200(client: TestClient) -> None:
    r = client.get("/api/cost-trend/compare?period1=2024-01&period2=2024-02")
    assert r.status_code == 200


def test_api_cost_trend_compare_shape(client: TestClient) -> None:
    body = client.get("/api/cost-trend/compare?period1=2024-01&period2=2024-02").json()
    assert "items" in body
    assert "summary" in body
    assert "period1" in body
    assert "period2" in body
    s = body["summary"]
    assert "total_period1" in s
    assert "total_period2" in s
    assert "total_change" in s


def test_api_cost_trend_compare_with_team_filter(client: TestClient) -> None:
    r = client.get("/api/cost-trend/compare?period1=2024-01&period2=2024-02&team=platform")
    assert r.status_code == 200


def test_definitions_has_cost_trend_asset() -> None:
    from dagster_project.definitions import defs
    asset_keys = [str(a.key) for a in defs.assets]  # type: ignore[union-attr]
    assert any("cost_trend" in k for k in asset_keys)
