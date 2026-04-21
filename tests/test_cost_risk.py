"""Tests for Phase 25 — /api/cost-risk endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_cost_risk_returns_200(client: TestClient) -> None:
    r = client.get("/api/cost-risk")
    assert r.status_code == 200


def test_cost_risk_shape(client: TestClient) -> None:
    body = client.get("/api/cost-risk").json()
    assert "billing_month" in body
    assert "items" in body
    assert "summary" in body
    s = body["summary"]
    assert "total_resources" in s
    assert "total_cost" in s
    assert "total_anomalies" in s
    assert "has_anomaly_data" in s


def test_cost_risk_items_fields(client: TestClient) -> None:
    body = client.get("/api/cost-risk").json()
    for item in body["items"]:
        assert "resource_id" in item
        assert "team" in item
        assert "env" in item
        assert "provider" in item
        assert "total_cost" in item
        assert "anomaly_count" in item
        assert "risk_score" in item
        assert item["total_cost"] >= 0
        assert item["anomaly_count"] >= 0


def test_cost_risk_with_billing_month(client: TestClient) -> None:
    r = client.get("/api/cost-risk?billing_month=2024-01")
    assert r.status_code == 200
    body = r.json()
    assert body["billing_month"] == "2024-01"


def test_cost_risk_with_provider_filter(client: TestClient) -> None:
    r = client.get("/api/cost-risk?provider=aws")
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["provider"] == "aws"


def test_cost_risk_with_team_filter(client: TestClient) -> None:
    r = client.get("/api/cost-risk?team=platform")
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["team"] == "platform"


def test_cost_risk_limit_param(client: TestClient) -> None:
    r = client.get("/api/cost-risk?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 5


def test_cost_risk_min_anomaly_zero_returns_items(client: TestClient) -> None:
    body = client.get("/api/cost-risk?min_anomaly_count=0").json()
    assert isinstance(body["items"], list)


def test_cost_risk_risk_score_non_negative(client: TestClient) -> None:
    body = client.get("/api/cost-risk?min_anomaly_count=0").json()
    for item in body["items"]:
        assert item["risk_score"] >= 0


def test_cost_risk_summary_counts_match_items(client: TestClient) -> None:
    body = client.get("/api/cost-risk?min_anomaly_count=0").json()
    assert body["summary"]["total_resources"] == len(body["items"])
