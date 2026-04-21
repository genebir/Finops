"""Tests for /api/ops endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_ops_live(client: TestClient) -> None:
    r = client.get("/api/ops/live")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body


def test_ops_ready(client: TestClient) -> None:
    r = client.get("/api/ops/ready")
    assert r.status_code in (200, 503)
    body = r.json()
    assert "status" in body


def test_ops_health(client: TestClient) -> None:
    r = client.get("/api/ops/health")
    assert r.status_code == 200
    body = r.json()
    assert "db_reachable" in body
    assert "tables" in body
    assert isinstance(body["tables"], list)


def test_ops_runs_default(client: TestClient) -> None:
    r = client.get("/api/ops/runs")
    assert r.status_code == 200
    body = r.json()
    assert "runs" in body
    assert "success_count" in body
    assert "failure_count" in body
    assert isinstance(body["runs"], list)


def test_ops_runs_limit(client: TestClient) -> None:
    r = client.get("/api/ops/runs?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert len(body["runs"]) <= 5


def test_ops_metrics(client: TestClient) -> None:
    r = client.get("/api/ops/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    text = r.text
    assert "finops_" in text


def test_health_endpoint(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_request_id_header(client: TestClient) -> None:
    r = client.get("/api/ops/live")
    assert "x-request-id" in r.headers
