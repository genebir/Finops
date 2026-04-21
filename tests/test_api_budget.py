"""Tests for /api/budget endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_budget_returns_200(client: TestClient) -> None:
    r = client.get("/api/budget")
    assert r.status_code == 200


def test_budget_shape(client: TestClient) -> None:
    body = client.get("/api/budget").json()
    assert "items" in body
    assert "total_budget" in body
    assert "total_actual" in body
    assert isinstance(body["items"], list)


def test_budget_total_non_negative(client: TestClient) -> None:
    body = client.get("/api/budget").json()
    assert body["total_budget"] >= 0
    assert body["total_actual"] >= 0


def test_budget_item_fields(client: TestClient) -> None:
    body = client.get("/api/budget").json()
    for item in body["items"]:
        assert "team" in item
        assert "env" in item
        assert "budget_amount" in item
        assert "actual_cost" in item
        assert "used_pct" in item
        assert "status" in item


def test_budget_item_status_values(client: TestClient) -> None:
    body = client.get("/api/budget").json()
    valid_statuses = {"over", "warning", "on_track", "no_budget", "under", "ok"}
    for item in body["items"]:
        assert item["status"] in valid_statuses


def test_budget_entries_returns_200(client: TestClient) -> None:
    r = client.get("/api/budget/entries")
    assert r.status_code == 200


def test_budget_entries_shape(client: TestClient) -> None:
    body = client.get("/api/budget/entries").json()
    assert "items" in body
    assert isinstance(body["items"], list)


def test_budget_crud_create_update_delete(client: TestClient) -> None:
    team = "test_api_budget_37"
    env = "dev"
    # Create
    r = client.post("/api/budget", json={"team": team, "env": env, "budget_amount": 500.0})
    assert r.status_code == 201
    # Update
    r = client.put(
        f"/api/budget/{team}/{env}",
        json={"budget_amount": 600.0},
        params={"billing_month": "default"},
    )
    assert r.status_code == 200
    assert r.json()["budget_amount"] == 600.0
    # Delete
    r = client.delete(f"/api/budget/{team}/{env}", params={"billing_month": "default"})
    assert r.status_code == 204


def test_budget_create_conflict(client: TestClient) -> None:
    team = "test_api_budget_conflict_37"
    env = "prod"
    client.post("/api/budget", json={"team": team, "env": env, "budget_amount": 100.0})
    r = client.post("/api/budget", json={"team": team, "env": env, "budget_amount": 200.0})
    assert r.status_code == 409
    # Cleanup
    client.delete(f"/api/budget/{team}/{env}", params={"billing_month": "default"})
