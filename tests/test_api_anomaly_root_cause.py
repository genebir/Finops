"""Tests for Phase 45 — /api/anomaly-root-cause endpoint."""
from __future__ import annotations

from collections.abc import Iterable

import psycopg2
import pytest
from fastapi.testclient import TestClient

from api.main import app
from dagster_project.config import load_config
from dagster_project.db_schema import ensure_tables

_PREFIX = "test_arc_"  # all rows in this test file use this resource_id prefix
_TARGET_DATE = "2024-04-15"
_BASELINE_START = "2024-04-08"  # 7 days before target


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
    ensure_tables(conn, "fact_daily_cost")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM fact_daily_cost WHERE resource_id LIKE %s", (_PREFIX + "%",))
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM fact_daily_cost WHERE resource_id LIKE %s", (_PREFIX + "%",))
    conn.close()


def _insert(
    conn,
    rows: Iterable[tuple[str, str, str, str, str, float]],
) -> None:
    """Insert (resource_id, charge_date, service_name, team, env, cost) rows."""
    with conn.cursor() as cur:
        for resource_id, charge_date, service_name, team, env, cost in rows:
            cur.execute(
                """
                INSERT INTO fact_daily_cost (
                    provider, charge_date, resource_id, resource_name,
                    service_name, service_category, region_id,
                    team, product, env, cost_unit_key,
                    effective_cost, billed_cost, list_cost, record_count
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    "aws", charge_date, resource_id, resource_id,
                    service_name, "Compute", "us-east-1",
                    team, "prod_x", env, f"{team}:prod_x:{env}",
                    cost, cost, cost, 1,
                ),
            )


def _baseline_days() -> list[str]:
    return [f"2024-04-{d:02d}" for d in range(8, 15)]  # 04-08..04-14


# ----- 1) 404 + basic shape -----------------------------------------------------------------

def test_returns_404_when_resource_missing_on_date(client: TestClient, pg_conn) -> None:
    r = client.get(
        "/api/anomaly-root-cause",
        params={"resource_id": _PREFIX + "ghost", "charge_date": _TARGET_DATE},
    )
    assert r.status_code == 404


def test_response_shape(client: TestClient, pg_conn) -> None:
    rid = _PREFIX + "shape"
    _insert(pg_conn, [(rid, _TARGET_DATE, "EC2", "shape_team", "prod", 100.0)])
    body = client.get(
        "/api/anomaly-root-cause",
        params={"resource_id": rid, "charge_date": _TARGET_DATE},
    ).json()
    for key in (
        "resource_id", "charge_date", "service_name", "team", "env", "provider",
        "target_cost", "history", "peers", "team_context", "root_cause",
    ):
        assert key in body, f"missing key {key}"
    assert body["root_cause"]["cause"] in {"new_resource", "cost_spike", "peer_spike", "unknown"}
    assert 0.0 <= body["root_cause"]["confidence"] <= 1.0


# ----- 2) Cause classifications -------------------------------------------------------------

def test_new_resource_when_no_baseline(client: TestClient, pg_conn) -> None:
    rid = _PREFIX + "new_res"
    _insert(pg_conn, [(rid, _TARGET_DATE, "EC2", "new_team", "prod", 500.0)])
    body = client.get(
        "/api/anomaly-root-cause",
        params={"resource_id": rid, "charge_date": _TARGET_DATE},
    ).json()
    assert body["root_cause"]["cause"] == "new_resource"
    assert body["history"]["days_observed"] == 0
    assert body["history"]["spike_ratio"] is None
    assert body["root_cause"]["confidence"] >= 0.8


def test_cost_spike_when_isolated(client: TestClient, pg_conn) -> None:
    rid = _PREFIX + "spike_iso"
    rows = [(rid, d, "EC2", "spike_team", "prod", 100.0) for d in _baseline_days()]
    rows.append((rid, _TARGET_DATE, "EC2", "spike_team", "prod", 1000.0))  # 10x baseline
    _insert(pg_conn, rows)
    body = client.get(
        "/api/anomaly-root-cause",
        params={"resource_id": rid, "charge_date": _TARGET_DATE},
    ).json()
    assert body["root_cause"]["cause"] == "cost_spike"
    assert body["history"]["spike_ratio"] >= 9.5
    assert body["root_cause"]["confidence"] >= 0.6


def test_peer_spike_when_peers_also_jump(client: TestClient, pg_conn) -> None:
    target = _PREFIX + "peer_target"
    peer_a = _PREFIX + "peer_a"
    peer_b = _PREFIX + "peer_b"
    service = "EC2"
    team = "peer_team"

    rows: list[tuple[str, str, str, str, str, float]] = []
    # baseline week — all three resources at 100/day
    for d in _baseline_days():
        rows.append((target, d, service, team, "prod", 100.0))
        rows.append((peer_a, d, service, team, "prod", 100.0))
        rows.append((peer_b, d, service, team, "prod", 100.0))
    # event day — every resource jumps ~5x
    rows.append((target, _TARGET_DATE, service, team, "prod", 500.0))
    rows.append((peer_a, _TARGET_DATE, service, team, "prod", 500.0))
    rows.append((peer_b, _TARGET_DATE, service, team, "prod", 500.0))
    _insert(pg_conn, rows)

    body = client.get(
        "/api/anomaly-root-cause",
        params={"resource_id": target, "charge_date": _TARGET_DATE},
    ).json()
    assert body["root_cause"]["cause"] == "peer_spike"
    assert body["peers"]["peer_count"] == 2
    assert body["peers"]["peers_also_spiked"] is True


def test_unknown_when_cost_within_normal_range(client: TestClient, pg_conn) -> None:
    rid = _PREFIX + "normal"
    rows = [(rid, d, "EC2", "calm_team", "prod", 100.0) for d in _baseline_days()]
    rows.append((rid, _TARGET_DATE, "EC2", "calm_team", "prod", 110.0))  # only 1.1x
    _insert(pg_conn, rows)
    body = client.get(
        "/api/anomaly-root-cause",
        params={"resource_id": rid, "charge_date": _TARGET_DATE},
    ).json()
    assert body["root_cause"]["cause"] == "unknown"


# ----- 3) Sub-section content checks --------------------------------------------------------

def test_history_summary_values(client: TestClient, pg_conn) -> None:
    rid = _PREFIX + "hist"
    rows = [(rid, d, "EC2", "hist_team", "prod", 50.0) for d in _baseline_days()]
    rows.append((rid, _TARGET_DATE, "EC2", "hist_team", "prod", 200.0))
    _insert(pg_conn, rows)
    body = client.get(
        "/api/anomaly-root-cause",
        params={"resource_id": rid, "charge_date": _TARGET_DATE},
    ).json()
    h = body["history"]
    assert h["days_observed"] == 7
    assert h["avg_prior_7d"] == 50.0
    assert h["max_prior_7d"] == 50.0
    assert h["min_prior_7d"] == 50.0
    assert h["spike_ratio"] == 4.0
    assert body["target_cost"] == 200.0


def test_team_context_change_pct(client: TestClient, pg_conn) -> None:
    rid = _PREFIX + "team_ctx"
    rows = [(rid, d, "EC2", "ctx_team", "prod", 100.0) for d in _baseline_days()]
    rows.append((rid, _TARGET_DATE, "EC2", "ctx_team", "prod", 200.0))  # team doubled today
    _insert(pg_conn, rows)
    body = client.get(
        "/api/anomaly-root-cause",
        params={"resource_id": rid, "charge_date": _TARGET_DATE},
    ).json()
    tc = body["team_context"]
    assert tc["team"] == "ctx_team"
    assert tc["team_total_today"] == 200.0
    assert tc["team_avg_prior_7d"] == 100.0
    assert tc["team_change_pct"] == 100.0


def test_peer_count_excludes_self(client: TestClient, pg_conn) -> None:
    target = _PREFIX + "self"
    peer = _PREFIX + "neighbor"
    _insert(
        pg_conn,
        [
            (target, _TARGET_DATE, "S3", "self_team", "prod", 100.0),
            (peer, _TARGET_DATE, "S3", "self_team", "prod", 50.0),
        ],
    )
    body = client.get(
        "/api/anomaly-root-cause",
        params={"resource_id": target, "charge_date": _TARGET_DATE},
    ).json()
    assert body["peers"]["peer_count"] == 1
    assert body["peers"]["peer_avg_cost"] == 50.0


# ----- 4) Input validation ------------------------------------------------------------------

def test_missing_resource_id_returns_422(client: TestClient) -> None:
    r = client.get("/api/anomaly-root-cause", params={"charge_date": _TARGET_DATE})
    assert r.status_code == 422


def test_invalid_date_returns_422(client: TestClient) -> None:
    r = client.get(
        "/api/anomaly-root-cause",
        params={"resource_id": "anything", "charge_date": "not-a-date"},
    )
    assert r.status_code == 422
