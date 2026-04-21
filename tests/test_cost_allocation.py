"""Tests for Phase 17 — cost allocation rules CRUD and API endpoint."""
from __future__ import annotations

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
    ensure_tables(conn, "dim_allocation_rules", "dim_allocated_cost")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dim_allocation_rules WHERE resource_id LIKE 'test_alloc_%'")
    conn.close()


# ── DB tests ───────────────────────────────────────────────────────────────────

def test_allocation_rules_table_created(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_allocation_rules'"
        )
        assert cur.fetchone() is not None


def test_allocated_cost_table_created(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_allocated_cost'"
        )
        assert cur.fetchone() is not None


# ── API CRUD tests ─────────────────────────────────────────────────────────────

def test_list_rules_empty_ok(client: TestClient) -> None:
    r = client.get("/api/cost-allocation/rules")
    assert r.status_code == 200
    assert "items" in r.json()


def test_create_rule(client: TestClient) -> None:
    body = {"resource_id": "test_alloc_001", "team": "platform", "split_pct": 60.0}
    r = client.post("/api/cost-allocation/rules", json=body)
    assert r.status_code == 201
    data = r.json()
    assert data["resource_id"] == "test_alloc_001"
    assert data["split_pct"] == 60.0


def test_create_rule_invalid_pct(client: TestClient) -> None:
    body = {"resource_id": "test_alloc_bad", "team": "platform", "split_pct": 110.0}
    r = client.post("/api/cost-allocation/rules", json=body)
    assert r.status_code == 422


def test_update_rule(client: TestClient) -> None:
    # Create first
    body = {"resource_id": "test_alloc_002", "team": "data", "split_pct": 30.0}
    created = client.post("/api/cost-allocation/rules", json=body).json()
    rule_id = created["id"]

    # Update
    r = client.put(f"/api/cost-allocation/rules/{rule_id}", json={"split_pct": 40.0})
    assert r.status_code == 200
    assert r.json()["split_pct"] == 40.0


def test_delete_rule(client: TestClient) -> None:
    body = {"resource_id": "test_alloc_003", "team": "infra", "split_pct": 50.0}
    created = client.post("/api/cost-allocation/rules", json=body).json()
    rule_id = created["id"]

    r = client.delete(f"/api/cost-allocation/rules/{rule_id}")
    assert r.status_code == 204


def test_delete_nonexistent_rule(client: TestClient) -> None:
    r = client.delete("/api/cost-allocation/rules/9999999")
    assert r.status_code == 404


def test_get_allocated_costs(client: TestClient) -> None:
    r = client.get("/api/cost-allocation")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "billing_month" in body
    assert "total_allocated" in body


def test_get_allocated_costs_with_month(client: TestClient) -> None:
    r = client.get("/api/cost-allocation?billing_month=2025-01")
    assert r.status_code == 200
    assert r.json()["billing_month"] == "2025-01"


def test_definitions_has_cost_allocation_asset() -> None:
    from dagster_project.definitions import defs
    asset_keys = [str(a.key) for a in defs.assets]  # type: ignore[union-attr]
    assert any("cost_allocation" in k for k in asset_keys)
