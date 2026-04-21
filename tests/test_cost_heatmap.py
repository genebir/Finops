"""Tests for Phase 24 — /api/cost-heatmap endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_cost_heatmap_returns_200(client: TestClient) -> None:
    r = client.get("/api/cost-heatmap")
    assert r.status_code == 200


def test_cost_heatmap_shape(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    assert "billing_month" in body
    assert "dates" in body
    assert "teams" in body
    assert "matrix" in body
    assert "max_cost" in body
    assert isinstance(body["dates"], list)
    assert isinstance(body["teams"], list)
    assert isinstance(body["matrix"], list)


def test_cost_heatmap_matrix_row_length_matches_dates(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    n_dates = len(body["dates"])
    for row in body["matrix"]:
        assert len(row["values"]) == n_dates, f"Row {row['team']} has wrong length"


def test_cost_heatmap_teams_match_matrix(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    matrix_teams = [r["team"] for r in body["matrix"]]
    assert sorted(matrix_teams) == sorted(body["teams"])


def test_cost_heatmap_max_cost_accurate(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    if body["matrix"]:
        all_vals = [v for row in body["matrix"] for v in row["values"]]
        assert abs(body["max_cost"] - max(all_vals)) < 0.01


def test_cost_heatmap_with_billing_month(client: TestClient) -> None:
    r = client.get("/api/cost-heatmap?billing_month=2024-01")
    assert r.status_code == 200
    body = r.json()
    assert body["billing_month"] == "2024-01"


def test_cost_heatmap_with_provider_filter(client: TestClient) -> None:
    r = client.get("/api/cost-heatmap?provider=aws")
    assert r.status_code == 200


def test_cost_heatmap_with_team_filter(client: TestClient) -> None:
    r = client.get("/api/cost-heatmap?team=platform")
    assert r.status_code == 200
    body = r.json()
    for row in body["matrix"]:
        assert row["team"] == "platform"


def test_cost_heatmap_dates_chronological(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    dates = body["dates"]
    assert dates == sorted(dates)


def test_cost_heatmap_non_negative_values(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    for row in body["matrix"]:
        for v in row["values"]:
            assert v >= 0
