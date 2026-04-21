"""Tests for /api/cost-explorer endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_cost_explorer_returns_200(client: TestClient) -> None:
    r = client.get("/api/cost-explorer")
    assert r.status_code == 200


def test_cost_explorer_shape(client: TestClient) -> None:
    body = client.get("/api/cost-explorer").json()
    assert "daily" in body
    assert "by_service" in body
    assert "by_provider" in body
    assert "total" in body
    assert "avg_daily" in body
    assert isinstance(body["daily"], list)
    assert isinstance(body["by_service"], list)
    assert isinstance(body["by_provider"], list)


def test_cost_explorer_total_non_negative(client: TestClient) -> None:
    body = client.get("/api/cost-explorer").json()
    assert body["total"] >= 0
    assert body["avg_daily"] >= 0


def test_cost_explorer_daily_fields(client: TestClient) -> None:
    body = client.get("/api/cost-explorer").json()
    for day in body["daily"]:
        assert "charge_date" in day
        assert "cost" in day
        assert day["cost"] >= 0


def test_cost_explorer_by_service_fields(client: TestClient) -> None:
    body = client.get("/api/cost-explorer").json()
    for svc in body["by_service"]:
        assert "service_name" in svc
        assert "cost" in svc
        assert "pct" in svc


def test_cost_explorer_by_provider_fields(client: TestClient) -> None:
    body = client.get("/api/cost-explorer").json()
    for prov in body["by_provider"]:
        assert "provider" in prov
        assert "cost" in prov
        assert "pct" in prov


def test_cost_explorer_team_filter(client: TestClient) -> None:
    r = client.get("/api/cost-explorer?team=platform")
    assert r.status_code == 200


def test_cost_explorer_provider_filter(client: TestClient) -> None:
    r = client.get("/api/cost-explorer?provider=aws")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 0


def test_cost_explorer_env_filter(client: TestClient) -> None:
    r = client.get("/api/cost-explorer?env=prod")
    assert r.status_code == 200


def test_cost_explorer_date_range(client: TestClient) -> None:
    r = client.get("/api/cost-explorer?start=2024-01-01&end=2024-01-31")
    assert r.status_code == 200
