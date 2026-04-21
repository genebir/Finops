"""Tests for /api/cost-heatmap endpoint."""
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


def test_cost_heatmap_max_cost_non_negative(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    assert body["max_cost"] >= 0


def test_cost_heatmap_matrix_row_fields(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    for row in body["matrix"]:
        assert "team" in row
        assert "values" in row
        assert isinstance(row["values"], list)


def test_cost_heatmap_matrix_values_length(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    date_count = len(body["dates"])
    for row in body["matrix"]:
        assert len(row["values"]) == date_count


def test_cost_heatmap_values_non_negative(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    for row in body["matrix"]:
        for v in row["values"]:
            assert v >= 0


def test_cost_heatmap_max_cost_matches_matrix(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    if body["matrix"]:
        computed_max = max(v for row in body["matrix"] for v in row["values"])
        assert abs(body["max_cost"] - computed_max) < 0.1


def test_cost_heatmap_dates_sorted(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    dates = body["dates"]
    assert dates == sorted(dates)


def test_cost_heatmap_provider_filter(client: TestClient) -> None:
    r = client.get("/api/cost-heatmap?provider=aws")
    assert r.status_code == 200


def test_cost_heatmap_team_filter(client: TestClient) -> None:
    body = client.get("/api/cost-heatmap").json()
    if body["teams"]:
        team = body["teams"][0]
        r = client.get(f"/api/cost-heatmap?team={team}")
        assert r.status_code == 200
        filtered = r.json()
        # filtered matrix should only have this team
        for row in filtered["matrix"]:
            assert row["team"] == team
