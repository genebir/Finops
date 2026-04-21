"""Tests for /api/overview endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_overview_returns_200(client: TestClient) -> None:
    r = client.get("/api/overview")
    assert r.status_code == 200


def test_overview_shape(client: TestClient) -> None:
    body = client.get("/api/overview").json()
    assert "total_cost" in body
    assert "cost_by_team" in body
    assert "top_resources" in body
    assert "anomaly_count" in body
    assert "resource_count" in body
    assert isinstance(body["cost_by_team"], list)
    assert isinstance(body["top_resources"], list)


def test_overview_total_cost_non_negative(client: TestClient) -> None:
    body = client.get("/api/overview").json()
    assert body["total_cost"] >= 0


def test_overview_cost_by_team_fields(client: TestClient) -> None:
    body = client.get("/api/overview").json()
    for entry in body["cost_by_team"]:
        assert "team" in entry
        assert "cost" in entry
        assert "pct" in entry
        assert entry["cost"] >= 0


def test_overview_top_resources_fields(client: TestClient) -> None:
    body = client.get("/api/overview").json()
    for r in body["top_resources"]:
        assert "resource_id" in r
        assert "cost" in r
        assert r["cost"] >= 0


def test_overview_with_provider_filter(client: TestClient) -> None:
    r = client.get("/api/overview?provider=aws")
    assert r.status_code == 200
    body = r.json()
    assert body["total_cost"] >= 0


def test_overview_with_date_range(client: TestClient) -> None:
    r = client.get("/api/overview?start=2024-01-01&end=2024-01-31")
    assert r.status_code == 200


def test_overview_anomaly_count_non_negative(client: TestClient) -> None:
    body = client.get("/api/overview").json()
    assert body["anomaly_count"] >= 0


def test_overview_resource_count_non_negative(client: TestClient) -> None:
    body = client.get("/api/overview").json()
    assert body["resource_count"] >= 0


def test_overview_cost_pct_sum(client: TestClient) -> None:
    body = client.get("/api/overview").json()
    if body["cost_by_team"]:
        total_pct = sum(t["pct"] for t in body["cost_by_team"])
        assert abs(total_pct - 100.0) < 1.5
