"""Tests for Phase 20 — dim_alert_history persistence and /api/alerts endpoints."""
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
    ensure_tables(conn, "dim_alert_history")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dim_alert_history WHERE resource_id LIKE 'test_alert_%'")
    conn.close()


def _insert_alert(
    conn,
    resource_id: str = "test_alert_res1",
    severity: str = "warning",
    alert_type: str = "anomaly",
) -> int:
    now = datetime.datetime.now(datetime.UTC)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dim_alert_history
                (alert_type, severity, resource_id, cost_unit_key,
                 message, actual_cost, reference_cost, deviation_pct, triggered_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (alert_type, severity, resource_id, "platform:api:prod",
             "Test alert message", 100.0, 80.0, 25.0, now),
        )
        row = cur.fetchone()
    assert row is not None
    return int(row[0])


def test_alert_history_table_exists(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_alert_history'"
        )
        assert cur.fetchone() is not None


def test_alert_history_insert_read(pg_conn) -> None:
    alert_id = _insert_alert(pg_conn)
    with pg_conn.cursor() as cur:
        cur.execute("SELECT severity, acknowledged FROM dim_alert_history WHERE id = %s", (alert_id,))
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "warning"
    assert row[1] is False


def test_alert_history_default_not_acknowledged(pg_conn) -> None:
    alert_id = _insert_alert(pg_conn, resource_id="test_alert_res2")
    with pg_conn.cursor() as cur:
        cur.execute("SELECT acknowledged, acknowledged_at FROM dim_alert_history WHERE id = %s", (alert_id,))
        row = cur.fetchone()
    assert row is not None
    assert row[0] is False
    assert row[1] is None


def test_api_alerts_returns_200(client: TestClient) -> None:
    r = client.get("/api/alerts")
    assert r.status_code == 200


def test_api_alerts_shape(client: TestClient) -> None:
    body = client.get("/api/alerts").json()
    assert "items" in body
    assert "total" in body
    assert "summary" in body
    s = body["summary"]
    assert "critical" in s
    assert "warning" in s
    assert "unacknowledged" in s


def test_api_alerts_severity_filter(client: TestClient) -> None:
    r = client.get("/api/alerts?severity=critical")
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["severity"] == "critical"


def test_api_alerts_acknowledged_filter(client: TestClient) -> None:
    r = client.get("/api/alerts?acknowledged=false")
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["acknowledged"] is False


def test_api_alerts_alert_type_filter(client: TestClient) -> None:
    r = client.get("/api/alerts?alert_type=anomaly")
    assert r.status_code == 200


def test_api_alerts_limit_param(client: TestClient) -> None:
    r = client.get("/api/alerts?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 5


def test_api_alerts_acknowledge_not_found(client: TestClient) -> None:
    r = client.post("/api/alerts/999999999/acknowledge", json={"acknowledged_by": "test"})
    assert r.status_code == 404


def test_api_alerts_acknowledge_workflow(client: TestClient, pg_conn) -> None:
    alert_id = _insert_alert(pg_conn, resource_id="test_alert_ack", severity="critical")

    r = client.post(f"/api/alerts/{alert_id}/acknowledge", json={"acknowledged_by": "test_user"})
    assert r.status_code == 200
    body = r.json()
    assert body["acknowledged"] is True
    assert body["acknowledged_by"] == "test_user"
    assert body["acknowledged_at"] is not None
    assert body["id"] == alert_id


def test_api_alerts_item_fields(client: TestClient, pg_conn) -> None:
    _insert_alert(pg_conn, resource_id="test_alert_fields")
    body = client.get("/api/alerts").json()
    if body["items"]:
        item = body["items"][0]
        assert "id" in item
        assert "alert_type" in item
        assert "severity" in item
        assert "resource_id" in item
        assert "message" in item
        assert "triggered_at" in item
        assert "acknowledged" in item


def test_definitions_has_alert_dispatch_asset() -> None:
    from dagster_project.definitions import defs
    asset_keys = [str(a.key) for a in defs.assets]  # type: ignore[union-attr]
    assert any("alert_dispatch" in k for k in asset_keys)
