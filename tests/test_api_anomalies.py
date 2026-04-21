"""Tests for /api/anomalies endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_anomalies_returns_200(client: TestClient) -> None:
    r = client.get("/api/anomalies")
    assert r.status_code == 200


def test_anomalies_shape(client: TestClient) -> None:
    body = client.get("/api/anomalies").json()
    assert "items" in body
    assert "total" in body
    assert "critical" in body
    assert "warning" in body
    assert isinstance(body["items"], list)


def test_anomalies_counts_non_negative(client: TestClient) -> None:
    body = client.get("/api/anomalies").json()
    assert body["total"] >= 0
    assert body["critical"] >= 0
    assert body["warning"] >= 0


def test_anomalies_severity_filter_critical(client: TestClient) -> None:
    r = client.get("/api/anomalies?severity=critical")
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["severity"] == "critical"


def test_anomalies_severity_filter_warning(client: TestClient) -> None:
    r = client.get("/api/anomalies?severity=warning")
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["severity"] == "warning"


def test_anomalies_team_filter(client: TestClient) -> None:
    r = client.get("/api/anomalies?team=platform")
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["team"] == "platform"


def test_anomalies_item_fields(client: TestClient) -> None:
    body = client.get("/api/anomalies").json()
    for item in body["items"]:
        assert "resource_id" in item
        assert "team" in item
        assert "severity" in item
        assert "charge_date" in item


def test_anomalies_env_filter(client: TestClient) -> None:
    r = client.get("/api/anomalies?env=prod")
    assert r.status_code == 200


def test_anomalies_limit_param(client: TestClient) -> None:
    r = client.get("/api/anomalies?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 5
