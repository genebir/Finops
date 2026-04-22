"""Tests for /api/pipeline/* endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_pipeline_assets_returns_200(client: TestClient) -> None:
    r = client.get("/api/pipeline/assets")
    assert r.status_code == 200


def test_pipeline_assets_shape(client: TestClient) -> None:
    body = client.get("/api/pipeline/assets").json()
    assert "assets" in body
    assert "total" in body
    assert isinstance(body["assets"], list)
    assert body["total"] > 0


def test_pipeline_assets_fields(client: TestClient) -> None:
    body = client.get("/api/pipeline/assets").json()
    for a in body["assets"]:
        assert "key" in a
        assert "group" in a
        assert "description" in a
        assert "has_partitions" in a


def test_pipeline_assets_known_groups(client: TestClient) -> None:
    body = client.get("/api/pipeline/assets").json()
    groups = {a["group"] for a in body["assets"] if a["group"]}
    known = {"ingestion", "transform", "marts", "analytics", "forecast", "budget", "compliance", "support"}
    assert groups.issubset(known)


def test_pipeline_presets_returns_200(client: TestClient) -> None:
    r = client.get("/api/pipeline/presets")
    assert r.status_code == 200


def test_pipeline_presets_shape(client: TestClient) -> None:
    body = client.get("/api/pipeline/presets").json()
    assert isinstance(body, list)
    assert len(body) > 0
    for p in body:
        assert "name" in p
        assert "description" in p
        assert "assets" in p
        assert isinstance(p["assets"], list)


def test_pipeline_presets_known_names(client: TestClient) -> None:
    body = client.get("/api/pipeline/presets").json()
    names = {p["name"] for p in body}
    assert "full_ingestion" in names
    assert "analytics" in names


def test_trigger_unknown_asset_400(client: TestClient) -> None:
    r = client.post(
        "/api/pipeline/trigger",
        json={"assets": ["nonexistent_asset"], "partition_key": "2024-01-01"},
    )
    assert r.status_code == 400
    assert "Unknown assets" in r.json()["detail"]


def test_trigger_missing_partition_key_400(client: TestClient) -> None:
    r = client.post(
        "/api/pipeline/trigger",
        json={"assets": ["raw_cur"]},
    )
    assert r.status_code == 400
    assert "partition_key" in r.json()["detail"]


def test_trigger_single_asset_success(client: TestClient) -> None:
    """Trigger a single raw_cur asset — should succeed."""
    r = client.post(
        "/api/pipeline/trigger",
        json={"assets": ["raw_cur"], "partition_key": "2024-01-01"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["succeeded"] == 1
    assert body["failed"] == 0
    assert body["results"][0]["asset_key"] == "raw_cur"
    assert body["results"][0]["success"] is True
    assert body["results"][0]["duration_sec"] is not None


def test_trigger_fx_rates_success(client: TestClient) -> None:
    """Trigger fx_rates asset."""
    r = client.post(
        "/api/pipeline/trigger",
        json={"assets": ["fx_rates"], "partition_key": "2024-01-01"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["succeeded"] >= 1


def test_trigger_response_shape(client: TestClient) -> None:
    r = client.post(
        "/api/pipeline/trigger",
        json={"assets": ["raw_cur"], "partition_key": "2024-02-01"},
    )
    body = r.json()
    assert "results" in body
    assert "total" in body
    assert "succeeded" in body
    assert "failed" in body
    for result in body["results"]:
        assert "asset_key" in result
        assert "success" in result
        assert "error" in result
        assert "duration_sec" in result
