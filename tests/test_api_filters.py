"""Tests for /api/filters endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_filters_returns_200(client: TestClient) -> None:
    r = client.get("/api/filters")
    assert r.status_code == 200


def test_filters_shape(client: TestClient) -> None:
    body = client.get("/api/filters").json()
    assert "teams" in body
    assert "envs" in body
    assert "providers" in body
    assert "services" in body
    assert "billing_months" in body
    assert isinstance(body["teams"], list)
    assert isinstance(body["envs"], list)
    assert isinstance(body["providers"], list)
    assert isinstance(body["services"], list)
    assert isinstance(body["billing_months"], list)


def test_filters_providers_known_values(client: TestClient) -> None:
    body = client.get("/api/filters").json()
    for prov in body["providers"]:
        assert prov in {"aws", "gcp", "azure"}


def test_filters_envs_non_empty(client: TestClient) -> None:
    body = client.get("/api/filters").json()
    assert len(body["envs"]) > 0


def test_filters_teams_non_empty(client: TestClient) -> None:
    body = client.get("/api/filters").json()
    assert len(body["teams"]) > 0


def test_filters_billing_months_sorted(client: TestClient) -> None:
    body = client.get("/api/filters").json()
    months = body["billing_months"]
    assert months == sorted(months) or months == sorted(months, reverse=True)


def test_filters_date_range(client: TestClient) -> None:
    body = client.get("/api/filters").json()
    assert "date_min" in body
    assert "date_max" in body
