"""Tests for Phase 44 — /api/alert-rules CRUD endpoint."""
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
    ensure_tables(conn, "dim_alert_rules")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dim_alert_rules WHERE rule_name LIKE 'test_ar_%'")
    conn.close()


def test_alert_rules_table_exists(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_alert_rules'"
        )
        assert cur.fetchone() is not None


def test_list_returns_200(client: TestClient, pg_conn) -> None:
    r = client.get("/api/alert-rules")
    assert r.status_code == 200


def test_list_shape(client: TestClient, pg_conn) -> None:
    body = client.get("/api/alert-rules").json()
    assert "items" in body
    assert "total" in body
    assert "summary" in body
    assert isinstance(body["items"], list)
    s = body["summary"]
    assert "enabled" in s
    assert "disabled" in s
    assert "total" in s


def test_create_rule(client: TestClient, pg_conn) -> None:
    body = {
        "rule_name": "test_ar_create_basic",
        "team": "platform",
        "metric": "cost_spike",
        "threshold": 500.0,
        "severity": "warning",
    }
    r = client.post("/api/alert-rules", json=body)
    assert r.status_code == 201
    data = r.json()
    assert data["rule_name"] == "test_ar_create_basic"
    assert data["team"] == "platform"
    assert data["metric"] == "cost_spike"
    assert data["threshold"] == 500.0
    assert data["severity"] == "warning"
    assert data["enabled"] is True
    assert data["id"] > 0


def test_create_duplicate_returns_409(client: TestClient, pg_conn) -> None:
    body = {
        "rule_name": "test_ar_dup",
        "metric": "anomaly_count",
        "threshold": 5.0,
    }
    r1 = client.post("/api/alert-rules", json=body)
    assert r1.status_code == 201
    r2 = client.post("/api/alert-rules", json=body)
    assert r2.status_code == 409


def test_create_invalid_metric_returns_422(client: TestClient, pg_conn) -> None:
    body = {
        "rule_name": "test_ar_bad_metric",
        "metric": "not_a_metric",
        "threshold": 1.0,
    }
    r = client.post("/api/alert-rules", json=body)
    assert r.status_code == 422


def test_create_invalid_severity_returns_422(client: TestClient, pg_conn) -> None:
    body = {
        "rule_name": "test_ar_bad_sev",
        "metric": "cost_spike",
        "threshold": 1.0,
        "severity": "info",
    }
    r = client.post("/api/alert-rules", json=body)
    assert r.status_code == 422


def test_create_negative_threshold_returns_422(client: TestClient, pg_conn) -> None:
    body = {
        "rule_name": "test_ar_neg",
        "metric": "cost_spike",
        "threshold": -10.0,
    }
    r = client.post("/api/alert-rules", json=body)
    assert r.status_code == 422


def test_update_rule(client: TestClient, pg_conn) -> None:
    body = {
        "rule_name": "test_ar_update",
        "metric": "budget_pct",
        "threshold": 80.0,
    }
    created = client.post("/api/alert-rules", json=body).json()
    rule_id = created["id"]

    r = client.put(
        f"/api/alert-rules/{rule_id}",
        json={"threshold": 120.0, "severity": "critical", "enabled": False},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["threshold"] == 120.0
    assert updated["severity"] == "critical"
    assert updated["enabled"] is False
    assert updated["rule_name"] == "test_ar_update"


def test_update_nonexistent_returns_404(client: TestClient, pg_conn) -> None:
    r = client.put("/api/alert-rules/9999999", json={"threshold": 1.0})
    assert r.status_code == 404


def test_update_empty_returns_400(client: TestClient, pg_conn) -> None:
    body = {
        "rule_name": "test_ar_empty",
        "metric": "cost_spike",
        "threshold": 1.0,
    }
    created = client.post("/api/alert-rules", json=body).json()
    r = client.put(f"/api/alert-rules/{created['id']}", json={})
    assert r.status_code == 400


def test_delete_rule(client: TestClient, pg_conn) -> None:
    body = {
        "rule_name": "test_ar_delete",
        "metric": "cost_spike",
        "threshold": 50.0,
    }
    created = client.post("/api/alert-rules", json=body).json()
    rule_id = created["id"]

    r = client.delete(f"/api/alert-rules/{rule_id}")
    assert r.status_code == 204


def test_delete_nonexistent_returns_404(client: TestClient, pg_conn) -> None:
    r = client.delete("/api/alert-rules/9999999")
    assert r.status_code == 404


def test_team_filter(client: TestClient, pg_conn) -> None:
    client.post("/api/alert-rules", json={
        "rule_name": "test_ar_team_alpha",
        "team": "alpha-team",
        "metric": "cost_spike",
        "threshold": 1.0,
    })
    client.post("/api/alert-rules", json={
        "rule_name": "test_ar_team_beta",
        "team": "beta-team",
        "metric": "cost_spike",
        "threshold": 1.0,
    })
    r = client.get("/api/alert-rules?team=alpha-team")
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(it["team"] == "alpha-team" for it in items)
    assert any(it["rule_name"] == "test_ar_team_alpha" for it in items)


def test_enabled_filter(client: TestClient, pg_conn) -> None:
    created = client.post("/api/alert-rules", json={
        "rule_name": "test_ar_enabled_filter",
        "metric": "cost_spike",
        "threshold": 1.0,
    }).json()
    client.put(f"/api/alert-rules/{created['id']}", json={"enabled": False})

    r = client.get("/api/alert-rules?enabled=false")
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(it["enabled"] is False for it in items)
