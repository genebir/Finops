"""Tests for /api/forecast endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_forecast_returns_200(client: TestClient) -> None:
    r = client.get("/api/forecast")
    assert r.status_code == 200


def test_forecast_shape(client: TestClient) -> None:
    body = client.get("/api/forecast").json()
    assert "items" in body
    assert "total_forecast" in body
    assert "total_actual" in body
    assert isinstance(body["items"], list)


def test_forecast_totals_non_negative(client: TestClient) -> None:
    body = client.get("/api/forecast").json()
    assert body["total_forecast"] >= 0
    assert body["total_actual"] >= 0


def test_forecast_item_fields(client: TestClient) -> None:
    body = client.get("/api/forecast").json()
    for item in body["items"]:
        assert "resource_id" in item
        assert "monthly_forecast" in item
        assert "lower_bound" in item
        assert "upper_bound" in item
        assert "source" in item


def test_forecast_source_values(client: TestClient) -> None:
    body = client.get("/api/forecast").json()
    valid_sources = {"prophet", "infracost"}
    for item in body["items"]:
        assert item["source"] in valid_sources


def test_forecast_bounds_ordering(client: TestClient) -> None:
    body = client.get("/api/forecast").json()
    for item in body["items"]:
        assert item["lower_bound"] <= item["monthly_forecast"]
        assert item["monthly_forecast"] <= item["upper_bound"]
