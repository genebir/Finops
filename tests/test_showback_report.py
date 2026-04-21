"""Tests for Phase 18 — showback report asset and API endpoint."""
from __future__ import annotations

import datetime
import json

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
    ensure_tables(conn, "dim_showback_report")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dim_showback_report WHERE team = 'test_showback_team'")
    conn.close()


def _insert_report(conn, month: str, team: str, cost: float) -> None:
    now = datetime.datetime.now(datetime.UTC)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dim_showback_report
              (billing_month, team, total_cost, budget_amount, utilization_pct,
               anomaly_count, top_services, top_resources, generated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                month, team, cost, 10000.0, cost / 100.0,
                2,
                json.dumps([{"service": "EC2", "cost": cost * 0.6}]),
                json.dumps([{"resource_id": "r-001", "resource_name": "web", "cost": cost * 0.4}]),
                now,
            ),
        )


def test_showback_table_created(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_showback_report'"
        )
        assert cur.fetchone() is not None


def test_showback_insert_read(pg_conn) -> None:
    _insert_report(pg_conn, "2026-04", "test_showback_team", 5000.0)
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT total_cost, anomaly_count FROM dim_showback_report WHERE team='test_showback_team'"
        )
        row = cur.fetchone()
    assert row is not None
    assert abs(row[0] - 5000.0) < 0.1
    assert row[1] == 2


def test_api_showback_returns_200(client: TestClient) -> None:
    r = client.get("/api/showback")
    assert r.status_code == 200


def test_api_showback_shape(client: TestClient) -> None:
    body = client.get("/api/showback").json()
    assert "teams" in body
    assert "billing_month" in body
    assert "total_cost" in body


def test_api_showback_with_month(client: TestClient) -> None:
    r = client.get("/api/showback?billing_month=2025-01")
    assert r.status_code == 200
    assert r.json()["billing_month"] == "2025-01"


def test_api_showback_with_team_filter(client: TestClient) -> None:
    r = client.get("/api/showback?team=platform")
    assert r.status_code == 200
    body = r.json()
    for t in body["teams"]:
        assert t["team"] == "platform"


def test_api_showback_top_services_is_list(client: TestClient) -> None:
    r = client.get("/api/showback")
    body = r.json()
    for team in body["teams"]:
        assert isinstance(team["top_services"], list)
        assert isinstance(team["top_resources"], list)


def test_api_showback_export_returns_json(client: TestClient) -> None:
    r = client.get("/api/showback/export")
    assert r.status_code == 200
    assert "application/json" in r.headers["content-type"]
    assert "showback_" in r.headers.get("content-disposition", "")


def test_definitions_has_showback_asset() -> None:
    from dagster_project.definitions import defs
    asset_keys = [str(a.key) for a in defs.assets]  # type: ignore[union-attr]
    assert any("showback_report" in k for k in asset_keys)
