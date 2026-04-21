"""Tests for /api/chargeback endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_chargeback_returns_200(client: TestClient) -> None:
    r = client.get("/api/chargeback")
    assert r.status_code == 200


def test_chargeback_shape(client: TestClient) -> None:
    body = client.get("/api/chargeback").json()
    assert "billing_month" in body
    assert "available_months" in body
    assert "total_cost" in body
    assert "by_team" in body
    assert "items" in body
    assert isinstance(body["by_team"], list)
    assert isinstance(body["items"], list)
    assert isinstance(body["available_months"], list)


def test_chargeback_total_non_negative(client: TestClient) -> None:
    body = client.get("/api/chargeback").json()
    assert body["total_cost"] >= 0


def test_chargeback_by_team_fields(client: TestClient) -> None:
    body = client.get("/api/chargeback").json()
    for entry in body["by_team"]:
        assert "team" in entry
        assert "cost" in entry
        assert "pct" in entry
        assert entry["cost"] >= 0


def test_chargeback_item_fields(client: TestClient) -> None:
    body = client.get("/api/chargeback").json()
    for item in body["items"]:
        assert "team" in item
        assert "product" in item
        assert "env" in item
        assert "cost" in item
        assert "pct" in item


def test_chargeback_pct_sums_to_100(client: TestClient) -> None:
    body = client.get("/api/chargeback").json()
    if body["by_team"]:
        total_pct = sum(t["pct"] for t in body["by_team"])
        assert abs(total_pct - 100.0) < 1.0


def test_chargeback_billing_month_filter(client: TestClient) -> None:
    body = client.get("/api/chargeback").json()
    months = body["available_months"]
    if months:
        r = client.get(f"/api/chargeback?billing_month={months[0]}")
        assert r.status_code == 200
        filtered = r.json()
        assert filtered["billing_month"] == months[0]
