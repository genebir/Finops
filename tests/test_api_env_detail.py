"""Tests for /api/environments/{env} endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _pick_env(client: TestClient) -> str | None:
    body = client.get("/api/filters").json()
    envs = body.get("envs", [])
    return envs[0] if envs else None


def test_env_detail_returns_200(client: TestClient) -> None:
    env = _pick_env(client)
    if not env:
        pytest.skip("no env data")
    r = client.get(f"/api/environments/{env}")
    assert r.status_code == 200


def test_env_detail_404_unknown(client: TestClient) -> None:
    r = client.get("/api/environments/nonexistent_env_xyz")
    assert r.status_code == 404


def test_env_detail_shape(client: TestClient) -> None:
    env = _pick_env(client)
    if not env:
        pytest.skip("no env data")
    body = client.get(f"/api/environments/{env}").json()
    assert body["env"] == env
    assert "latest_month" in body
    assert "monthly_trend" in body
    assert "by_team" in body
    assert "by_provider" in body
    assert "by_service" in body
    assert "top_resources" in body
    assert "summary" in body


def test_env_detail_summary_fields(client: TestClient) -> None:
    env = _pick_env(client)
    if not env:
        pytest.skip("no env data")
    s = client.get(f"/api/environments/{env}").json()["summary"]
    assert "curr_cost" in s
    assert "prev_cost" in s
    assert "mom_change_pct" in s
    assert "resource_count" in s
    assert "team_count" in s
    assert s["curr_cost"] >= 0
    assert s["team_count"] >= 0


def test_env_detail_monthly_trend(client: TestClient) -> None:
    env = _pick_env(client)
    if not env:
        pytest.skip("no env data")
    trend = client.get(f"/api/environments/{env}").json()["monthly_trend"]
    assert isinstance(trend, list)
    if trend:
        assert "billing_month" in trend[0]
        assert "total_cost" in trend[0]
        assert "resource_count" in trend[0]
        months = [t["billing_month"] for t in trend]
        assert months == sorted(months)


def test_env_detail_by_team_sorted(client: TestClient) -> None:
    env = _pick_env(client)
    if not env:
        pytest.skip("no env data")
    by_team = client.get(f"/api/environments/{env}").json()["by_team"]
    costs = [t["cost"] for t in by_team]
    assert costs == sorted(costs, reverse=True)


def test_env_detail_by_team_pct(client: TestClient) -> None:
    env = _pick_env(client)
    if not env:
        pytest.skip("no env data")
    by_team = client.get(f"/api/environments/{env}").json()["by_team"]
    if by_team:
        total_pct = sum(t["pct"] for t in by_team)
        assert 99.0 <= total_pct <= 101.0


def test_env_detail_by_service_sorted(client: TestClient) -> None:
    env = _pick_env(client)
    if not env:
        pytest.skip("no env data")
    by_service = client.get(f"/api/environments/{env}").json()["by_service"]
    costs = [s["cost"] for s in by_service]
    assert costs == sorted(costs, reverse=True)
    if by_service:
        assert "service_name" in by_service[0]
        assert "pct" in by_service[0]


def test_env_detail_top_resources_fields(client: TestClient) -> None:
    env = _pick_env(client)
    if not env:
        pytest.skip("no env data")
    resources = client.get(f"/api/environments/{env}").json()["top_resources"]
    for r in resources:
        assert "resource_id" in r
        assert "team" in r
        assert "provider" in r
        assert "cost" in r
        assert r["cost"] >= 0


def test_env_detail_months_param(client: TestClient) -> None:
    env = _pick_env(client)
    if not env:
        pytest.skip("no env data")
    body3 = client.get(f"/api/environments/{env}?months=3").json()
    body12 = client.get(f"/api/environments/{env}?months=12").json()
    assert len(body3["monthly_trend"]) <= 3
    assert len(body12["monthly_trend"]) <= 12
