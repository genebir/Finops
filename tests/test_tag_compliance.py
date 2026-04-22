"""Tests for Phase 31 — /api/tag-compliance endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_tag_compliance_returns_200(client: TestClient) -> None:
    r = client.get("/api/tag-compliance")
    assert r.status_code == 200


def test_tag_compliance_shape(client: TestClient) -> None:
    body = client.get("/api/tag-compliance").json()
    assert "billing_month" in body
    assert "summary" in body
    assert "teams" in body
    assert isinstance(body["teams"], list)


def test_tag_compliance_summary_fields(client: TestClient) -> None:
    body = client.get("/api/tag-compliance").json()
    s = body["summary"]
    assert "avg_score" in s
    assert "perfect_count" in s
    assert "below_threshold_count" in s
    assert "total_teams" in s
    assert s["avg_score"] >= 0
    assert s["perfect_count"] >= 0
    assert s["below_threshold_count"] >= 0


def test_tag_compliance_team_fields(client: TestClient) -> None:
    body = client.get("/api/tag-compliance").json()
    for row in body["teams"]:
        assert "team" in row
        assert "provider" in row
        assert "total_resources" in row
        assert "tagged_resources" in row
        assert "violation_count" in row
        assert "tag_completeness" in row
        assert "compliance_score" in row
        assert "rank" in row
        assert 0 <= row["compliance_score"] <= 100
        assert 0 <= row["tag_completeness"] <= 100
        assert row["tagged_resources"] <= row["total_resources"]


def test_tag_compliance_with_billing_month(client: TestClient) -> None:
    r = client.get("/api/tag-compliance?billing_month=2024-01")
    assert r.status_code == 200


def test_tag_compliance_with_provider_filter(client: TestClient) -> None:
    r = client.get("/api/tag-compliance?provider=aws")
    assert r.status_code == 200
    body = r.json()
    for row in body["teams"]:
        assert row["provider"] == "aws"


def test_tag_compliance_with_team_filter(client: TestClient) -> None:
    body = client.get("/api/tag-compliance").json()
    if not body["teams"]:
        pytest.skip("no data")
    first_team = body["teams"][0]["team"]
    r = client.get(f"/api/tag-compliance?team={first_team}")
    assert r.status_code == 200
    for row in r.json()["teams"]:
        assert row["team"] == first_team


def test_tag_compliance_scores_ordered_desc(client: TestClient) -> None:
    body = client.get("/api/tag-compliance").json()
    scores = [row["compliance_score"] for row in body["teams"]]
    assert scores == sorted(scores, reverse=True)


def test_tag_compliance_rank_sequence(client: TestClient) -> None:
    body = client.get("/api/tag-compliance").json()
    ranks = [row["rank"] for row in body["teams"]]
    if ranks:
        assert all(isinstance(r, int) and r >= 1 for r in ranks)


def test_tag_compliance_empty_month_returns_200(client: TestClient) -> None:
    r = client.get("/api/tag-compliance?billing_month=1900-01")
    assert r.status_code == 200
