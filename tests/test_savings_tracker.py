"""Tests for Phase 23 — savings tracker asset and /api/savings endpoint."""
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
    ensure_tables(conn, "dim_savings_realized")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dim_savings_realized WHERE team = 'test_savings_team'")
    conn.close()


def _insert_savings(conn, month: str = "2026-01", status: str = "realized") -> None:
    now = datetime.datetime.now(datetime.UTC)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dim_savings_realized
                (billing_month, resource_id, team, product, env, provider,
                 recommendation_type, estimated_savings, realized_savings,
                 prev_month_cost, curr_month_cost, status, computed_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (month, "test_res_1", "test_savings_team", "api", "prod", "aws",
             "idle", 500.0, 480.0, 1200.0, 720.0, status, now),
        )


def test_savings_table_exists(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_savings_realized'"
        )
        assert cur.fetchone() is not None


def test_savings_schema(pg_conn) -> None:
    _insert_savings(pg_conn)
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT status, estimated_savings, realized_savings FROM dim_savings_realized WHERE team = 'test_savings_team'"
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "realized"
    assert abs(row[1] - 500.0) < 0.01
    assert abs(row[2] - 480.0) < 0.01


def test_api_savings_returns_200(client: TestClient) -> None:
    r = client.get("/api/savings")
    assert r.status_code == 200


def test_api_savings_shape(client: TestClient) -> None:
    body = client.get("/api/savings").json()
    assert "billing_month" in body
    assert "items" in body
    assert "summary" in body
    s = body["summary"]
    assert "total_estimated" in s
    assert "total_realized" in s
    assert "realized_count" in s
    assert "pending_count" in s


def test_api_savings_with_billing_month(client: TestClient) -> None:
    r = client.get("/api/savings?billing_month=2026-01")
    assert r.status_code == 200
    body = r.json()
    assert body["billing_month"] == "2026-01"


def test_api_savings_with_team_filter(client: TestClient) -> None:
    r = client.get("/api/savings?team=platform")
    assert r.status_code == 200


def test_api_savings_with_status_filter(client: TestClient) -> None:
    r = client.get("/api/savings?status=realized")
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["status"] == "realized"


def test_api_savings_item_fields(client: TestClient, pg_conn) -> None:
    _insert_savings(pg_conn, month="2026-02", status="partial")
    r = client.get("/api/savings?billing_month=2026-02")
    body = r.json()
    if body["items"]:
        item = body["items"][0]
        assert "resource_id" in item
        assert "team" in item
        assert "estimated_savings" in item
        assert "status" in item


def test_api_savings_summary_non_negative(client: TestClient) -> None:
    body = client.get("/api/savings").json()
    s = body["summary"]
    assert s["realized_count"] >= 0
    assert s["pending_count"] >= 0


def test_definitions_has_savings_tracker_asset() -> None:
    from dagster_project.definitions import defs
    asset_keys = [str(a.key) for a in defs.assets]  # type: ignore[union-attr]
    assert any("savings" in k for k in asset_keys)
