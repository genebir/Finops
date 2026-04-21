"""Tests for Phase 29 — budget_forecast asset and /api/budget-forecast endpoint."""
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
        host=cfg.postgres.host, port=cfg.postgres.port,
        dbname=cfg.postgres.dbname, user=cfg.postgres.user,
        password=cfg.postgres.password,
    )
    conn.autocommit = True
    ensure_tables(conn, "dim_budget_forecast")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dim_budget_forecast WHERE team = 'test_bfcast_team'")
    conn.close()


def _insert_forecast(conn, month: str = "2026-01", risk: str = "normal") -> None:
    now = datetime.datetime.now(datetime.UTC)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dim_budget_forecast
                (billing_month, team, env, days_elapsed, days_in_month,
                 mtd_cost, projected_eom, lower_bound, upper_bound,
                 budget_amount, projected_pct, risk_level, computed_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (month, "test_bfcast_team", "prod", 10, 31,
             5000.0, 15500.0, 12000.0, 19000.0,
             20000.0, 77.5, risk, now),
        )


def test_budget_forecast_table_exists(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_budget_forecast'"
        )
        assert cur.fetchone() is not None


def test_budget_forecast_schema(pg_conn) -> None:
    _insert_forecast(pg_conn)
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT projected_eom, risk_level FROM dim_budget_forecast WHERE team='test_bfcast_team'"
        )
        row = cur.fetchone()
    assert row is not None
    assert abs(row[0] - 15500.0) < 0.01
    assert row[1] == "normal"


def test_api_budget_forecast_returns_200(client: TestClient) -> None:
    r = client.get("/api/budget-forecast")
    assert r.status_code == 200


def test_api_budget_forecast_shape(client: TestClient) -> None:
    body = client.get("/api/budget-forecast").json()
    assert "billing_month" in body
    assert "items" in body
    assert "summary" in body
    s = body["summary"]
    assert "total_projected_eom" in s
    assert "over_budget_count" in s
    assert "warning_count" in s
    assert "normal_count" in s


def test_api_budget_forecast_with_billing_month(client: TestClient) -> None:
    r = client.get("/api/budget-forecast?billing_month=2026-01")
    assert r.status_code == 200
    body = r.json()
    assert body["billing_month"] == "2026-01"


def test_api_budget_forecast_with_team_filter(client: TestClient) -> None:
    r = client.get("/api/budget-forecast?team=platform")
    assert r.status_code == 200


def test_api_budget_forecast_with_risk_filter(client: TestClient) -> None:
    r = client.get("/api/budget-forecast?risk_level=warning")
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["risk_level"] == "warning"


def test_api_budget_forecast_item_fields(client: TestClient, pg_conn) -> None:
    _insert_forecast(pg_conn, month="2026-03", risk="warning")
    r = client.get("/api/budget-forecast?billing_month=2026-03")
    body = r.json()
    if body["items"]:
        item = body["items"][0]
        assert "team" in item
        assert "env" in item
        assert "projected_eom" in item
        assert "lower_bound" in item
        assert "upper_bound" in item
        assert "risk_level" in item
        assert item["projected_eom"] >= 0


def test_api_budget_forecast_bounds_order(client: TestClient, pg_conn) -> None:
    _insert_forecast(pg_conn, month="2026-04")
    body = client.get("/api/budget-forecast?billing_month=2026-04").json()
    for item in body["items"]:
        assert item["lower_bound"] <= item["projected_eom"] <= item["upper_bound"]


def test_definitions_has_budget_forecast_asset() -> None:
    from dagster_project.definitions import defs
    asset_keys = [str(a.key) for a in defs.assets]  # type: ignore[union-attr]
    assert any("budget_forecast" in k for k in asset_keys)
