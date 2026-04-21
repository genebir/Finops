"""Tests for Phase 30 — /api/env-breakdown endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_env_breakdown_returns_200(client: TestClient) -> None:
    r = client.get("/api/env-breakdown")
    assert r.status_code == 200


def test_env_breakdown_shape(client: TestClient) -> None:
    body = client.get("/api/env-breakdown").json()
    assert "billing_month" in body
    assert "grand_total" in body
    assert "envs" in body
    assert "cross_tab" in body
    assert isinstance(body["envs"], list)
    assert isinstance(body["cross_tab"], list)


def test_env_breakdown_env_fields(client: TestClient) -> None:
    body = client.get("/api/env-breakdown").json()
    for env in body["envs"]:
        assert "env" in env
        assert "cost" in env
        assert "pct" in env
        assert "resource_count" in env
        assert "team_count" in env
        assert env["cost"] >= 0


def test_env_breakdown_pct_sums_to_100(client: TestClient) -> None:
    body = client.get("/api/env-breakdown").json()
    total = sum(e["pct"] for e in body["envs"])
    assert abs(total - 100.0) < 1.0


def test_env_breakdown_with_billing_month(client: TestClient) -> None:
    r = client.get("/api/env-breakdown?billing_month=2024-01")
    assert r.status_code == 200
    body = r.json()
    assert body["billing_month"] == "2024-01"


def test_env_breakdown_with_provider_filter(client: TestClient) -> None:
    r = client.get("/api/env-breakdown?provider=aws")
    assert r.status_code == 200


def test_env_breakdown_cross_tab_structure(client: TestClient) -> None:
    body = client.get("/api/env-breakdown").json()
    for row in body["cross_tab"]:
        assert "env" in row
        assert "by_team" in row
        assert isinstance(row["by_team"], dict)


def test_env_breakdown_grand_total_positive(client: TestClient) -> None:
    body = client.get("/api/env-breakdown").json()
    assert body["grand_total"] > 0


def test_env_breakdown_has_prod_env(client: TestClient) -> None:
    body = client.get("/api/env-breakdown").json()
    env_names = {e["env"] for e in body["envs"]}
    assert "prod" in env_names
