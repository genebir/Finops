"""Tests for Phase 22 — /api/cloud-compare multi-cloud comparison endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_cloud_compare_returns_200(client: TestClient) -> None:
    r = client.get("/api/cloud-compare")
    assert r.status_code == 200


def test_cloud_compare_shape(client: TestClient) -> None:
    body = client.get("/api/cloud-compare").json()
    assert "billing_month" in body
    assert "grand_total" in body
    assert "providers" in body
    assert "top_services_by_provider" in body
    assert "trend_by_provider" in body
    assert "teams" in body
    assert isinstance(body["providers"], list)
    assert isinstance(body["teams"], list)


def test_cloud_compare_provider_fields(client: TestClient) -> None:
    body = client.get("/api/cloud-compare").json()
    for prov in body["providers"]:
        assert "provider" in prov
        assert "total_cost" in prov
        assert "resource_count" in prov
        assert "pct" in prov


def test_cloud_compare_pct_sums_to_100(client: TestClient) -> None:
    body = client.get("/api/cloud-compare").json()
    total_pct = sum(p["pct"] for p in body["providers"])
    assert abs(total_pct - 100.0) < 1.0


def test_cloud_compare_with_billing_month(client: TestClient) -> None:
    r = client.get("/api/cloud-compare?billing_month=2024-01")
    assert r.status_code == 200
    body = r.json()
    assert body["billing_month"] == "2024-01"


def test_cloud_compare_with_team_filter(client: TestClient) -> None:
    r = client.get("/api/cloud-compare?team=platform")
    assert r.status_code == 200


def test_cloud_compare_grand_total_positive(client: TestClient) -> None:
    body = client.get("/api/cloud-compare").json()
    assert body["grand_total"] >= 0


def test_cloud_compare_trend_chronological(client: TestClient) -> None:
    body = client.get("/api/cloud-compare").json()
    for prov, trend in body["trend_by_provider"].items():
        months = [entry["month"] for entry in trend]
        assert months == sorted(months), f"Trend for {prov} not chronological"


def test_cloud_compare_top_services_structure(client: TestClient) -> None:
    body = client.get("/api/cloud-compare").json()
    for prov, services in body["top_services_by_provider"].items():
        assert isinstance(services, list)
        assert len(services) <= 5
        for svc in services:
            assert "service" in svc
            assert "cost" in svc


def test_cloud_compare_teams_structure(client: TestClient) -> None:
    body = client.get("/api/cloud-compare").json()
    for team in body["teams"]:
        assert "team" in team
        assert "by_provider" in team
        assert "total" in team
        assert team["total"] >= 0


def test_cloud_compare_providers_three_clouds(client: TestClient) -> None:
    body = client.get("/api/cloud-compare").json()
    provider_names = {p["provider"] for p in body["providers"]}
    assert provider_names >= {"aws", "gcp", "azure"}
