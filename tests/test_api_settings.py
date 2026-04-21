"""Tests for /api/settings endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_settings_returns_200(client: TestClient) -> None:
    r = client.get("/api/settings")
    assert r.status_code == 200


def test_settings_shape(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    assert "items" in body
    assert isinstance(body["items"], list)
    assert len(body["items"]) > 0


def test_settings_item_fields(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    for item in body["items"]:
        assert "key" in item
        assert "value" in item
        assert "value_type" in item


def test_settings_has_known_key(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    keys = {item["key"] for item in body["items"]}
    assert "anomaly.zscore.warning" in keys


def test_settings_crud(client: TestClient) -> None:
    key = "test.api.settings.phase37"
    # Create
    r = client.post("/api/settings", json={
        "key": key,
        "value": "42.0",
        "value_type": "float",
        "description": "Phase 37 test setting",
    })
    assert r.status_code == 201
    assert r.json()["key"] == key
    # Update
    r = client.put(f"/api/settings/{key}", json={"value": "99.0"})
    assert r.status_code == 200
    assert r.json()["value"] == "99.0"
    # Delete
    r = client.delete(f"/api/settings/{key}")
    assert r.status_code == 204
    # Confirm deleted
    body = client.get("/api/settings").json()
    keys = {item["key"] for item in body["items"]}
    assert key not in keys


def test_settings_create_conflict(client: TestClient) -> None:
    key = "test.api.settings.conflict.phase37"
    client.post("/api/settings", json={"key": key, "value": "1", "value_type": "int"})
    r = client.post("/api/settings", json={"key": key, "value": "2", "value_type": "int"})
    assert r.status_code == 409
    client.delete(f"/api/settings/{key}")


def test_settings_update_missing_key(client: TestClient) -> None:
    r = client.put("/api/settings/nonexistent.key.phase37", json={"value": "0"})
    assert r.status_code == 404


def test_settings_delete_missing_key(client: TestClient) -> None:
    r = client.delete("/api/settings/nonexistent.key.phase37")
    assert r.status_code == 404
