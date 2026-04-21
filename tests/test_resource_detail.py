"""Tests for Phase 26 — /api/resources/{resource_id} drill-down endpoint."""
from __future__ import annotations

import psycopg2
import pytest
from fastapi.testclient import TestClient

from api.main import app
from dagster_project.config import load_config


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def any_resource_id() -> str:
    """Return any resource_id that exists in fact_daily_cost."""
    cfg = load_config()
    conn = psycopg2.connect(
        host=cfg.postgres.host, port=cfg.postgres.port,
        dbname=cfg.postgres.dbname, user=cfg.postgres.user,
        password=cfg.postgres.password,
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT resource_id FROM fact_daily_cost LIMIT 1")
        row = cur.fetchone()
    conn.close()
    return row[0] if row else "aws_instance.web_1"


def test_resource_detail_returns_200(client: TestClient, any_resource_id: str) -> None:
    r = client.get(f"/api/resources/{any_resource_id}")
    assert r.status_code == 200


def test_resource_detail_shape(client: TestClient, any_resource_id: str) -> None:
    body = client.get(f"/api/resources/{any_resource_id}").json()
    assert "resource_id" in body
    assert "provider" in body
    assert "team" in body
    assert "env" in body
    assert "monthly_history" in body
    assert "daily_last30" in body
    assert "anomaly_history" in body
    assert "summary" in body


def test_resource_detail_summary_fields(client: TestClient, any_resource_id: str) -> None:
    body = client.get(f"/api/resources/{any_resource_id}").json()
    s = body["summary"]
    assert "total_cost" in s
    assert "avg_monthly_cost" in s
    assert "latest_month_cost" in s
    assert "anomaly_count" in s
    assert "months_tracked" in s
    assert s["total_cost"] >= 0
    assert s["months_tracked"] >= 1


def test_resource_detail_monthly_history_chronological(client: TestClient, any_resource_id: str) -> None:
    body = client.get(f"/api/resources/{any_resource_id}").json()
    months = [m["billing_month"] for m in body["monthly_history"]]
    assert months == sorted(months)


def test_resource_detail_daily_chronological(client: TestClient, any_resource_id: str) -> None:
    body = client.get(f"/api/resources/{any_resource_id}").json()
    dates = [d["date"] for d in body["daily_last30"]]
    assert dates == sorted(dates)


def test_resource_detail_not_found(client: TestClient) -> None:
    r = client.get("/api/resources/nonexistent_resource_xyz_abc_123")
    assert r.status_code == 404


def test_resource_detail_months_param(client: TestClient, any_resource_id: str) -> None:
    r = client.get(f"/api/resources/{any_resource_id}?months=3")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["months_tracked"] <= 3


def test_resource_detail_resource_id_matches(client: TestClient, any_resource_id: str) -> None:
    body = client.get(f"/api/resources/{any_resource_id}").json()
    assert body["resource_id"] == any_resource_id


def test_resource_detail_costs_non_negative(client: TestClient, any_resource_id: str) -> None:
    body = client.get(f"/api/resources/{any_resource_id}").json()
    for m in body["monthly_history"]:
        assert m["cost"] >= 0
    for d in body["daily_last30"]:
        assert d["cost"] >= 0
