"""Tests for /api/services/{service_name} endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_service_detail_returns_200(client: TestClient) -> None:
    all_svc = client.get("/api/service-breakdown").json()
    if not all_svc["by_service"]:
        pytest.skip("no service data")
    name = all_svc["by_service"][0]["service_name"]
    r = client.get(f"/api/services/{name}")
    assert r.status_code == 200


def test_service_detail_404_unknown(client: TestClient) -> None:
    r = client.get("/api/services/nonexistent_service_xyz")
    assert r.status_code == 404


def test_service_detail_shape(client: TestClient) -> None:
    all_svc = client.get("/api/service-breakdown").json()
    if not all_svc["by_service"]:
        pytest.skip("no service data")
    name = all_svc["by_service"][0]["service_name"]
    body = client.get(f"/api/services/{name}").json()
    assert body["service_name"] == name
    assert "latest_month" in body
    assert "monthly_trend" in body
    assert "by_team" in body
    assert "by_provider" in body
    assert "by_env" in body
    assert "top_resources" in body
    assert "summary" in body


def test_service_detail_summary_fields(client: TestClient) -> None:
    all_svc = client.get("/api/service-breakdown").json()
    if not all_svc["by_service"]:
        pytest.skip("no service data")
    name = all_svc["by_service"][0]["service_name"]
    s = client.get(f"/api/services/{name}").json()["summary"]
    assert "curr_cost" in s
    assert "prev_cost" in s
    assert "mom_change_pct" in s
    assert "resource_count" in s
    assert "team_count" in s
    assert s["curr_cost"] >= 0
    assert s["team_count"] >= 0


def test_service_detail_monthly_trend(client: TestClient) -> None:
    all_svc = client.get("/api/service-breakdown").json()
    if not all_svc["by_service"]:
        pytest.skip("no service data")
    name = all_svc["by_service"][0]["service_name"]
    trend = client.get(f"/api/services/{name}").json()["monthly_trend"]
    assert isinstance(trend, list)
    if trend:
        assert "billing_month" in trend[0]
        assert "total_cost" in trend[0]
        assert "resource_count" in trend[0]
        months = [t["billing_month"] for t in trend]
        assert months == sorted(months)


def test_service_detail_by_team_sorted(client: TestClient) -> None:
    all_svc = client.get("/api/service-breakdown").json()
    if not all_svc["by_service"]:
        pytest.skip("no service data")
    name = all_svc["by_service"][0]["service_name"]
    by_team = client.get(f"/api/services/{name}").json()["by_team"]
    costs = [t["cost"] for t in by_team]
    assert costs == sorted(costs, reverse=True)


def test_service_detail_by_team_pct(client: TestClient) -> None:
    all_svc = client.get("/api/service-breakdown").json()
    if not all_svc["by_service"]:
        pytest.skip("no service data")
    name = all_svc["by_service"][0]["service_name"]
    by_team = client.get(f"/api/services/{name}").json()["by_team"]
    if by_team:
        total_pct = sum(t["pct"] for t in by_team)
        assert 99.0 <= total_pct <= 101.0


def test_service_detail_top_resources_fields(client: TestClient) -> None:
    all_svc = client.get("/api/service-breakdown").json()
    if not all_svc["by_service"]:
        pytest.skip("no service data")
    name = all_svc["by_service"][0]["service_name"]
    resources = client.get(f"/api/services/{name}").json()["top_resources"]
    for r in resources:
        assert "resource_id" in r
        assert "team" in r
        assert "cost" in r
        assert r["cost"] >= 0


def test_service_detail_months_param(client: TestClient) -> None:
    all_svc = client.get("/api/service-breakdown").json()
    if not all_svc["by_service"]:
        pytest.skip("no service data")
    name = all_svc["by_service"][0]["service_name"]
    body3 = client.get(f"/api/services/{name}?months=3").json()
    body12 = client.get(f"/api/services/{name}?months=12").json()
    assert len(body3["monthly_trend"]) <= 3
    assert len(body12["monthly_trend"]) <= 12


def test_service_detail_by_provider_fields(client: TestClient) -> None:
    all_svc = client.get("/api/service-breakdown").json()
    if not all_svc["by_service"]:
        pytest.skip("no service data")
    name = all_svc["by_service"][0]["service_name"]
    by_provider = client.get(f"/api/services/{name}").json()["by_provider"]
    for p in by_provider:
        assert "provider" in p
        assert "cost" in p
        assert "pct" in p
