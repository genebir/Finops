"""Tests for Phase 32 — /api/anomaly-timeline endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_anomaly_timeline_returns_200(client: TestClient) -> None:
    r = client.get("/api/anomaly-timeline")
    assert r.status_code == 200


def test_anomaly_timeline_shape(client: TestClient) -> None:
    body = client.get("/api/anomaly-timeline").json()
    assert "months" in body
    assert "series" in body
    assert "summary" in body
    assert "top_teams" in body
    assert isinstance(body["series"], list)
    assert isinstance(body["top_teams"], list)


def test_anomaly_timeline_summary_fields(client: TestClient) -> None:
    body = client.get("/api/anomaly-timeline").json()
    s = body["summary"]
    assert "total_anomalies" in s
    assert "peak_date" in s
    assert "peak_count" in s
    assert "avg_daily" in s
    assert s["total_anomalies"] >= 0
    assert s["peak_count"] >= 0
    assert s["avg_daily"] >= 0


def test_anomaly_timeline_series_fields(client: TestClient) -> None:
    body = client.get("/api/anomaly-timeline").json()
    for pt in body["series"]:
        assert "date" in pt
        assert "total" in pt
        assert "critical" in pt
        assert "warning" in pt
        assert "total_cost" in pt
        assert pt["total"] >= 0
        assert pt["critical"] + pt["warning"] <= pt["total"]


def test_anomaly_timeline_months_param(client: TestClient) -> None:
    r = client.get("/api/anomaly-timeline?months=3")
    assert r.status_code == 200
    body = r.json()
    assert body["months"] == 3


def test_anomaly_timeline_invalid_months(client: TestClient) -> None:
    r = client.get("/api/anomaly-timeline?months=0")
    assert r.status_code == 422


def test_anomaly_timeline_provider_filter(client: TestClient) -> None:
    r = client.get("/api/anomaly-timeline?provider=aws")
    assert r.status_code == 200


def test_anomaly_timeline_team_filter(client: TestClient) -> None:
    r = client.get("/api/anomaly-timeline?team=platform")
    assert r.status_code == 200


def test_anomaly_timeline_severity_filter(client: TestClient) -> None:
    r = client.get("/api/anomaly-timeline?severity=critical")
    assert r.status_code == 200
    body = r.json()
    for pt in body["series"]:
        assert pt["warning"] == 0


def test_anomaly_timeline_series_ordered_by_date(client: TestClient) -> None:
    body = client.get("/api/anomaly-timeline").json()
    dates = [pt["date"] for pt in body["series"]]
    assert dates == sorted(dates)
