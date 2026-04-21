"""Tests for /api/teams/{team} endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def sample_team(client: TestClient) -> str:
    """Return the first available team from leaderboard."""
    r = client.get("/api/leaderboard")
    assert r.status_code == 200
    items = r.json().get("items", [])
    if items:
        return str(items[0]["team"])
    pytest.skip("No teams available in test DB")


def test_team_detail_returns_200(client: TestClient, sample_team: str) -> None:
    r = client.get(f"/api/teams/{sample_team}")
    assert r.status_code == 200


def test_team_detail_404_unknown(client: TestClient) -> None:
    r = client.get("/api/teams/nonexistent_team_xyz_phase40")
    assert r.status_code == 404


def test_team_detail_shape(client: TestClient, sample_team: str) -> None:
    body = client.get(f"/api/teams/{sample_team}").json()
    assert "team" in body
    assert "latest_month" in body
    assert "monthly_trend" in body
    assert "by_service" in body
    assert "by_env" in body
    assert "by_provider" in body
    assert "top_resources" in body
    assert "anomalies" in body
    assert "summary" in body


def test_team_detail_team_matches(client: TestClient, sample_team: str) -> None:
    body = client.get(f"/api/teams/{sample_team}").json()
    assert body["team"] == sample_team


def test_team_detail_summary_fields(client: TestClient, sample_team: str) -> None:
    body = client.get(f"/api/teams/{sample_team}").json()
    summary = body["summary"]
    assert "curr_cost" in summary
    assert "prev_cost" in summary
    assert "mom_change_pct" in summary
    assert "resource_count" in summary
    assert "anomaly_count" in summary
    assert summary["curr_cost"] >= 0


def test_team_detail_monthly_trend_sorted(client: TestClient, sample_team: str) -> None:
    body = client.get(f"/api/teams/{sample_team}").json()
    months = [m["billing_month"] for m in body["monthly_trend"]]
    assert months == sorted(months)


def test_team_detail_by_service_pct(client: TestClient, sample_team: str) -> None:
    body = client.get(f"/api/teams/{sample_team}").json()
    for svc in body["by_service"]:
        assert "service_name" in svc
        assert "cost" in svc
        assert "pct" in svc
        assert svc["cost"] >= 0
        assert 0 <= svc["pct"] <= 100


def test_team_detail_by_env(client: TestClient, sample_team: str) -> None:
    body = client.get(f"/api/teams/{sample_team}").json()
    for env in body["by_env"]:
        assert "env" in env
        assert "cost" in env
        assert "pct" in env


def test_team_detail_top_resources(client: TestClient, sample_team: str) -> None:
    body = client.get(f"/api/teams/{sample_team}").json()
    for r in body["top_resources"]:
        assert "resource_id" in r
        assert "cost" in r
        assert r["cost"] >= 0


def test_team_detail_months_param(client: TestClient, sample_team: str) -> None:
    r = client.get(f"/api/teams/{sample_team}?months=3")
    assert r.status_code == 200
    body = r.json()
    assert len(body["monthly_trend"]) <= 3
