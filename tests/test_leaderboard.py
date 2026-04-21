"""Tests for Phase 27 — /api/leaderboard and /api/service-breakdown endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# --- /api/leaderboard ---

def test_leaderboard_returns_200(client: TestClient) -> None:
    r = client.get("/api/leaderboard")
    assert r.status_code == 200


def test_leaderboard_shape(client: TestClient) -> None:
    body = client.get("/api/leaderboard").json()
    assert "billing_month" in body
    assert "prev_month" in body
    assert "items" in body
    assert "summary" in body
    s = body["summary"]
    assert "total_curr" in s
    assert "total_prev" in s
    assert "team_count" in s


def test_leaderboard_items_fields(client: TestClient) -> None:
    body = client.get("/api/leaderboard").json()
    for item in body["items"]:
        assert "rank" in item
        assert "team" in item
        assert "curr_cost" in item
        assert "pct_of_total" in item
        assert "resource_count" in item
        assert item["rank"] >= 1
        assert item["curr_cost"] >= 0


def test_leaderboard_ranks_sequential(client: TestClient) -> None:
    body = client.get("/api/leaderboard").json()
    ranks = [i["rank"] for i in body["items"]]
    assert ranks == list(range(1, len(ranks) + 1))


def test_leaderboard_pct_sums_to_100(client: TestClient) -> None:
    body = client.get("/api/leaderboard").json()
    total_pct = sum(i["pct_of_total"] for i in body["items"])
    assert abs(total_pct - 100.0) < 1.5


def test_leaderboard_with_billing_month(client: TestClient) -> None:
    r = client.get("/api/leaderboard?billing_month=2024-01")
    assert r.status_code == 200
    body = r.json()
    assert body["billing_month"] == "2024-01"


def test_leaderboard_with_provider(client: TestClient) -> None:
    r = client.get("/api/leaderboard?provider=aws")
    assert r.status_code == 200


def test_leaderboard_limit_param(client: TestClient) -> None:
    r = client.get("/api/leaderboard?limit=3")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 3


# --- /api/service-breakdown ---

def test_service_breakdown_returns_200(client: TestClient) -> None:
    r = client.get("/api/service-breakdown")
    assert r.status_code == 200


def test_service_breakdown_shape(client: TestClient) -> None:
    body = client.get("/api/service-breakdown").json()
    assert "billing_month" in body
    assert "grand_total" in body
    assert "by_category" in body
    assert "by_service" in body
    assert isinstance(body["by_category"], list)
    assert isinstance(body["by_service"], list)


def test_service_breakdown_category_fields(client: TestClient) -> None:
    body = client.get("/api/service-breakdown").json()
    for cat in body["by_category"]:
        assert "category" in cat
        assert "cost" in cat
        assert "pct" in cat
        assert "resource_count" in cat


def test_service_breakdown_by_service_max_15(client: TestClient) -> None:
    body = client.get("/api/service-breakdown").json()
    assert len(body["by_service"]) <= 15


def test_service_breakdown_pct_sums_to_100(client: TestClient) -> None:
    body = client.get("/api/service-breakdown").json()
    total = sum(c["pct"] for c in body["by_category"])
    assert abs(total - 100.0) < 1.0


def test_service_breakdown_with_filters(client: TestClient) -> None:
    r = client.get("/api/service-breakdown?provider=aws&team=platform")
    assert r.status_code == 200


def test_service_breakdown_grand_total_positive(client: TestClient) -> None:
    body = client.get("/api/service-breakdown").json()
    assert body["grand_total"] > 0
