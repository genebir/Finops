"""Tests for Phase 15 — resource inventory asset and API endpoint."""
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
    ensure_tables(conn, "dim_resource_inventory")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dim_resource_inventory WHERE resource_id LIKE 'test_inv_%'")
    conn.close()


def _insert_resource(conn, resource_id: str, team: str | None, tags_complete: bool) -> None:
    now = datetime.datetime.now(datetime.UTC)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dim_resource_inventory
              (resource_id, resource_name, resource_type, service_name, service_category,
               region_id, provider, team, product, env, cost_unit_key,
               first_seen_date, last_seen_date, total_cost_30d,
               tags_complete, missing_tags, refreshed_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (resource_id) DO UPDATE SET refreshed_at = EXCLUDED.refreshed_at
            """,
            (
                resource_id, "Test Resource", "vm", "EC2", "Compute",
                "us-east-1", "aws", team, "core" if team else None,
                "prod", f"{team}:core:prod" if team else None,
                datetime.date.today(), datetime.date.today(), 500.0,
                tags_complete, None if tags_complete else "team",
                now,
            ),
        )


def test_inventory_table_created(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_resource_inventory'"
        )
        assert cur.fetchone() is not None


def test_inventory_insert_and_read(pg_conn) -> None:
    _insert_resource(pg_conn, "test_inv_001", "platform", True)
    with pg_conn.cursor() as cur:
        cur.execute("SELECT tags_complete FROM dim_resource_inventory WHERE resource_id='test_inv_001'")
        row = cur.fetchone()
    assert row is not None
    assert row[0] is True


def test_inventory_incomplete_tags(pg_conn) -> None:
    _insert_resource(pg_conn, "test_inv_002", None, False)
    with pg_conn.cursor() as cur:
        cur.execute("SELECT tags_complete, missing_tags FROM dim_resource_inventory WHERE resource_id='test_inv_002'")
        row = cur.fetchone()
    assert row is not None
    assert row[0] is False
    assert row[1] is not None


def test_api_inventory_returns_200(client: TestClient) -> None:
    r = client.get("/api/inventory")
    assert r.status_code == 200


def test_api_inventory_shape(client: TestClient) -> None:
    body = client.get("/api/inventory").json()
    assert "items" in body
    assert "summary" in body
    s = body["summary"]
    assert "total" in s
    assert "complete" in s
    assert "incomplete" in s
    assert "completeness_pct" in s


def test_api_inventory_summary_consistent(client: TestClient) -> None:
    body = client.get("/api/inventory").json()
    s = body["summary"]
    assert s["complete"] + s["incomplete"] == s["total"]


def test_api_inventory_filter_tags_complete(client: TestClient) -> None:
    r = client.get("/api/inventory?tags_complete=false")
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["tags_complete"] is False


def test_api_inventory_filter_provider(client: TestClient) -> None:
    r = client.get("/api/inventory?provider=aws")
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["provider"] == "aws"


def test_api_inventory_limit(client: TestClient) -> None:
    r = client.get("/api/inventory?limit=3")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 3


def test_definitions_has_resource_inventory() -> None:
    from dagster_project.definitions import defs
    asset_keys = [str(a.key) for a in defs.assets]  # type: ignore[union-attr]
    assert any("resource_inventory" in k for k in asset_keys)
