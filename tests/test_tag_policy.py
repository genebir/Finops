"""Tests for Phase 16 — tag policy asset and API endpoint."""
from __future__ import annotations

import datetime

import psycopg2
import pytest
from fastapi.testclient import TestClient

from api.main import app
from dagster_project.assets.tag_policy import _DEFAULT_POLICY, _load_policy, _severity
from dagster_project.config import load_config
from dagster_project.db_schema import ensure_tables
from dagster_project.resources.settings_store import SettingsStoreResource


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def pg_conn():
    cfg = load_config()
    conn = psycopg2.connect(
        host=cfg.postgres.host,
        port=cfg.postgres.port,
        dbname=cfg.postgres.dbname,
        user=cfg.postgres.user,
        password=cfg.postgres.password,
    )
    conn.autocommit = True
    ensure_tables(conn, "dim_tag_violations")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dim_tag_violations WHERE resource_id LIKE 'test_tp_%'")
    conn.close()


# ── Unit tests ─────────────────────────────────────────────────────────────────

def test_default_policy_has_wildcard() -> None:
    assert "*" in _DEFAULT_POLICY
    assert "team" in _DEFAULT_POLICY["*"]
    assert "env" in _DEFAULT_POLICY["*"]


def test_severity_high_cost() -> None:
    assert _severity(1, 2000.0) == "critical"


def test_severity_low_cost() -> None:
    assert _severity(1, 100.0) == "warning"


def test_severity_multiple_missing() -> None:
    assert _severity(2, 0.0) == "critical"


def test_load_policy_returns_default_when_empty() -> None:
    store = SettingsStoreResource()
    store.ensure_table()
    policy = _load_policy(store)
    assert "*" in policy


# ── DB tests ───────────────────────────────────────────────────────────────────

def test_dim_tag_violations_table_created(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_tag_violations'"
        )
        assert cur.fetchone() is not None


def test_dim_tag_violations_insert(pg_conn) -> None:
    now = datetime.datetime.now(datetime.UTC)
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dim_tag_violations
              (resource_id, resource_type, service_category, provider,
               team, env, violation_type, missing_tag, severity, cost_30d, detected_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            ("test_tp_001", "vm", "Compute", "aws",
             None, "prod", "missing_required_tag", "team", "critical", 1500.0, now),
        )
    with pg_conn.cursor() as cur:
        cur.execute("SELECT severity, missing_tag FROM dim_tag_violations WHERE resource_id='test_tp_001'")
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "critical"
    assert row[1] == "team"


# ── API tests ──────────────────────────────────────────────────────────────────

def test_api_tag_policy_returns_200(client: TestClient) -> None:
    r = client.get("/api/tag-policy")
    assert r.status_code == 200


def test_api_tag_policy_shape(client: TestClient) -> None:
    body = client.get("/api/tag-policy").json()
    assert "violations" in body
    assert "summary" in body
    s = body["summary"]
    assert "total" in s
    assert "critical" in s
    assert "warning" in s


def test_api_tag_policy_summary_consistent(client: TestClient) -> None:
    body = client.get("/api/tag-policy").json()
    s = body["summary"]
    assert s["critical"] + s["warning"] <= s["total"]


def test_api_tag_policy_filter_severity(client: TestClient) -> None:
    r = client.get("/api/tag-policy?severity=critical")
    assert r.status_code == 200
    body = r.json()
    for v in body["violations"]:
        assert v["severity"] == "critical"


def test_api_tag_policy_filter_provider(client: TestClient) -> None:
    r = client.get("/api/tag-policy?provider=aws")
    assert r.status_code == 200
    body = r.json()
    for v in body["violations"]:
        assert v["provider"] == "aws"


def test_definitions_has_tag_policy_asset() -> None:
    from dagster_project.definitions import defs
    asset_keys = [str(a.key) for a in defs.assets]  # type: ignore[union-attr]
    assert any("tag_policy" in k for k in asset_keys)
