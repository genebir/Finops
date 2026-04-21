"""Tests for /api/recommendations endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_recommendations_returns_200(client: TestClient) -> None:
    r = client.get("/api/recommendations")
    assert r.status_code == 200


def test_recommendations_shape(client: TestClient) -> None:
    body = client.get("/api/recommendations").json()
    assert "items" in body
    assert "total_potential_savings" in body
    assert isinstance(body["items"], list)


def test_recommendations_savings_non_negative(client: TestClient) -> None:
    body = client.get("/api/recommendations").json()
    assert body["total_potential_savings"] >= 0


def test_recommendations_item_fields(client: TestClient) -> None:
    body = client.get("/api/recommendations").json()
    for item in body["items"]:
        assert "rule_type" in item
        assert "resource_id" in item
        assert "team" in item
        assert "env" in item
        assert "potential_savings" in item
        assert "severity" in item


def test_recommendations_rule_type_values(client: TestClient) -> None:
    body = client.get("/api/recommendations").json()
    valid_types = {"idle", "high_growth", "persistent_anomaly"}
    for item in body["items"]:
        assert item["rule_type"] in valid_types


def test_recommendations_potential_savings_non_negative(client: TestClient) -> None:
    body = client.get("/api/recommendations").json()
    for item in body["items"]:
        assert item["potential_savings"] >= 0
