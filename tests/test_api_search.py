"""Tests for /api/search endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def sample_team(client: TestClient) -> str:
    r = client.get("/api/leaderboard")
    assert r.status_code == 200
    items = r.json().get("items", [])
    if items:
        return str(items[0]["team"])
    pytest.skip("No teams available in test DB")


def test_search_returns_200(client: TestClient) -> None:
    r = client.get("/api/search", params={"q": "a"})
    assert r.status_code == 200


def test_search_shape(client: TestClient) -> None:
    body = client.get("/api/search", params={"q": "a"}).json()
    assert "query" in body
    assert "resources" in body
    assert "teams" in body
    assert "services" in body
    assert "total" in body
    assert isinstance(body["resources"], list)
    assert isinstance(body["teams"], list)
    assert isinstance(body["services"], list)


def test_search_empty_query_returns_empty(client: TestClient) -> None:
    body = client.get("/api/search", params={"q": ""}).json()
    assert body["query"] == ""
    assert body["resources"] == []
    assert body["teams"] == []
    assert body["services"] == []
    assert body["total"] == 0


def test_search_whitespace_query_treated_as_empty(client: TestClient) -> None:
    body = client.get("/api/search", params={"q": "   "}).json()
    assert body["total"] == 0


def test_search_no_query_param_returns_empty(client: TestClient) -> None:
    body = client.get("/api/search").json()
    assert body["query"] == ""
    assert body["total"] == 0


def test_search_team_matches_case_insensitive(client: TestClient, sample_team: str) -> None:
    # Search by uppercase version of team name — ILIKE should still match
    body = client.get("/api/search", params={"q": sample_team.upper()}).json()
    matched_teams = [t["team"] for t in body["teams"]]
    assert sample_team in matched_teams


def test_search_team_substring_match(client: TestClient, sample_team: str) -> None:
    # Single-character substring should still find the team
    body = client.get("/api/search", params={"q": sample_team[:2]}).json()
    matched_teams = [t["team"] for t in body["teams"]]
    assert sample_team in matched_teams


def test_search_resources_have_expected_fields(client: TestClient) -> None:
    body = client.get("/api/search", params={"q": "i-"}).json()
    for r in body["resources"]:
        assert "resource_id" in r
        assert "service_name" in r
        assert "provider" in r
        assert "cost_30d" in r
        assert r["cost_30d"] >= 0


def test_search_teams_have_expected_fields(client: TestClient, sample_team: str) -> None:
    body = client.get("/api/search", params={"q": sample_team}).json()
    for t in body["teams"]:
        assert "team" in t
        assert "curr_month_cost" in t
        assert "resource_count" in t
        assert t["curr_month_cost"] >= 0


def test_search_services_have_expected_fields(client: TestClient) -> None:
    # Most fixtures include common services like EC2, S3, BigQuery, etc.
    body = client.get("/api/search", params={"q": "a"}).json()
    for s in body["services"]:
        assert "service_name" in s
        assert "curr_month_cost" in s
        assert s["curr_month_cost"] >= 0


def test_search_limit_caps_per_category(client: TestClient) -> None:
    # With limit=3, each category should be capped at limit//3 + 1 = 2
    body = client.get("/api/search", params={"q": "a", "limit": 3}).json()
    assert len(body["resources"]) <= 2
    assert len(body["teams"]) <= 2
    assert len(body["services"]) <= 2


def test_search_unknown_query_returns_empty_categories(client: TestClient) -> None:
    body = client.get("/api/search", params={"q": "zzz_phase43_no_match_xyz"}).json()
    assert body["resources"] == []
    assert body["teams"] == []
    assert body["services"] == []
    assert body["total"] == 0


def test_search_total_matches_sum(client: TestClient, sample_team: str) -> None:
    body = client.get("/api/search", params={"q": sample_team}).json()
    expected = len(body["resources"]) + len(body["teams"]) + len(body["services"])
    assert body["total"] == expected
