"""Variance 계산 단위 테스트 — 예측/실제 비용 편차 로직."""

from datetime import UTC, datetime
from decimal import Decimal

import psycopg2
import pytest

from dagster_project.assets.infracost_forecast import _parse_forecast_records
from dagster_project.config import load_config

_cfg = load_config()


def _get_test_conn() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(_cfg.postgres.dsn)
    conn.autocommit = True
    return conn


def _setup_test_tables(
    conn: psycopg2.extensions.connection,
    forecast_rows: list[dict],
    actual_rows: list[dict],
) -> None:
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS _test_dim_forecast CASCADE")
    cur.execute("DROP TABLE IF EXISTS _test_fact_daily_cost CASCADE")
    cur.execute("""
        CREATE TABLE _test_dim_forecast (
            resource_address      VARCHAR NOT NULL,
            monthly_cost          DECIMAL(18,6) NOT NULL,
            hourly_cost           DECIMAL(18,6) NOT NULL,
            currency              VARCHAR NOT NULL,
            forecast_generated_at TIMESTAMPTZ NOT NULL
        )
    """)
    for r in forecast_rows:
        cur.execute(
            "INSERT INTO _test_dim_forecast VALUES (%s, %s, %s, %s, %s)",
            [
                r["resource_address"],
                r["monthly_cost"],
                r["hourly_cost"],
                r.get("currency", "USD"),
                r.get("forecast_generated_at", datetime.now(tz=UTC).isoformat()),
            ],
        )

    cur.execute("""
        CREATE TABLE _test_fact_daily_cost (
            charge_date       DATE NOT NULL,
            resource_id       VARCHAR NOT NULL,
            effective_cost    DECIMAL(18,6)
        )
    """)
    for r in actual_rows:
        cur.execute(
            "INSERT INTO _test_fact_daily_cost VALUES (%s, %s, %s)",
            [r["charge_date"], r["resource_id"], r["effective_cost"]],
        )
    cur.close()


def _run_variance_query(
    conn: psycopg2.extensions.connection,
    billing_month: str,
    over_pct: float = 20.0,
    under_pct: float = 20.0,
) -> list[dict]:
    cur = conn.cursor()
    cur.execute("DROP VIEW IF EXISTS _test_v_variance")
    cur.execute(f"""
        CREATE VIEW _test_v_variance AS
        WITH actual_mtd AS (
            SELECT
                resource_id,
                DATE_TRUNC('month', charge_date) AS billing_month,
                SUM(effective_cost) AS actual_mtd
            FROM _test_fact_daily_cost
            GROUP BY resource_id, DATE_TRUNC('month', charge_date)
        )
        SELECT
            f.resource_address AS resource_id,
            f.monthly_cost AS forecast_monthly,
            COALESCE(a.actual_mtd, 0) AS actual_mtd,
            CASE
                WHEN f.monthly_cost = 0 THEN NULL
                ELSE (COALESCE(a.actual_mtd, 0) - f.monthly_cost) / f.monthly_cost * 100
            END AS variance_pct,
            CASE
                WHEN a.resource_id IS NULL THEN 'unmatched'
                WHEN (COALESCE(a.actual_mtd, 0) - f.monthly_cost)
                     / NULLIF(f.monthly_cost, 0) * 100 > {over_pct} THEN 'over'
                WHEN (COALESCE(a.actual_mtd, 0) - f.monthly_cost)
                     / NULLIF(f.monthly_cost, 0) * 100 < -{under_pct} THEN 'under'
                ELSE 'ok'
            END AS status,
            a.billing_month
        FROM _test_dim_forecast f
        LEFT JOIN actual_mtd a ON f.resource_address = a.resource_id
    """)
    cur.execute("""
        SELECT resource_id, forecast_monthly, actual_mtd, variance_pct, status
        FROM _test_v_variance
        WHERE billing_month = %s OR billing_month IS NULL
    """, [billing_month])
    cols = ["resource_id", "forecast_monthly", "actual_mtd", "variance_pct", "status"]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    return rows


def _cleanup(conn: psycopg2.extensions.connection) -> None:
    cur = conn.cursor()
    cur.execute("DROP VIEW IF EXISTS _test_v_variance")
    cur.execute("DROP TABLE IF EXISTS _test_dim_forecast")
    cur.execute("DROP TABLE IF EXISTS _test_fact_daily_cost")
    cur.close()


class TestVarianceStatus:
    def test_over_budget(self) -> None:
        conn = _get_test_conn()
        try:
            _setup_test_tables(
                conn,
                forecast_rows=[{"resource_address": "aws_instance.web_1", "monthly_cost": 100.0, "hourly_cost": 0.13}],
                actual_rows=[
                    {"charge_date": "2024-01-15", "resource_id": "aws_instance.web_1", "effective_cost": 150.0}
                ],
            )
            results = _run_variance_query(conn, "2024-01-01")
            assert len(results) == 1
            assert results[0]["status"] == "over"
            assert float(results[0]["variance_pct"]) == pytest.approx(50.0, abs=0.01)
        finally:
            _cleanup(conn)
            conn.close()

    def test_under_budget(self) -> None:
        conn = _get_test_conn()
        try:
            _setup_test_tables(
                conn,
                forecast_rows=[{"resource_address": "aws_instance.api_1", "monthly_cost": 100.0, "hourly_cost": 0.13}],
                actual_rows=[
                    {"charge_date": "2024-01-15", "resource_id": "aws_instance.api_1", "effective_cost": 60.0}
                ],
            )
            results = _run_variance_query(conn, "2024-01-01")
            assert len(results) == 1
            assert results[0]["status"] == "under"
            assert float(results[0]["variance_pct"]) == pytest.approx(-40.0, abs=0.01)
        finally:
            _cleanup(conn)
            conn.close()

    def test_ok_within_threshold(self) -> None:
        conn = _get_test_conn()
        try:
            _setup_test_tables(
                conn,
                forecast_rows=[{"resource_address": "aws_instance.ml_1", "monthly_cost": 100.0, "hourly_cost": 0.13}],
                actual_rows=[
                    {"charge_date": "2024-01-15", "resource_id": "aws_instance.ml_1", "effective_cost": 110.0}
                ],
            )
            results = _run_variance_query(conn, "2024-01-01")
            assert len(results) == 1
            assert results[0]["status"] == "ok"
        finally:
            _cleanup(conn)
            conn.close()

    def test_unmatched_no_actual(self) -> None:
        conn = _get_test_conn()
        try:
            _setup_test_tables(
                conn,
                forecast_rows=[{"resource_address": "aws_db_instance.main_1", "monthly_cost": 500.0, "hourly_cost": 0.69}],
                actual_rows=[],
            )
            results = _run_variance_query(conn, "2024-01-01")
            assert len(results) == 1
            assert results[0]["status"] == "unmatched"
        finally:
            _cleanup(conn)
            conn.close()

    def test_multiple_resources(self) -> None:
        conn = _get_test_conn()
        try:
            _setup_test_tables(
                conn,
                forecast_rows=[
                    {"resource_address": "aws_instance.web_1", "monthly_cost": 100.0, "hourly_cost": 0.13},
                    {"resource_address": "aws_instance.web_2", "monthly_cost": 100.0, "hourly_cost": 0.13},
                    {"resource_address": "aws_s3_bucket.assets_1", "monthly_cost": 15.0, "hourly_cost": 0.02},
                ],
                actual_rows=[
                    {"charge_date": "2024-01-15", "resource_id": "aws_instance.web_1", "effective_cost": 130.0},
                    {"charge_date": "2024-01-15", "resource_id": "aws_instance.web_2", "effective_cost": 70.0},
                ],
            )
            results = _run_variance_query(conn, "2024-01-01")
            statuses = {r["resource_id"]: r["status"] for r in results}
            assert statuses["aws_instance.web_1"] == "over"
            assert statuses["aws_instance.web_2"] == "under"
            assert statuses["aws_s3_bucket.assets_1"] == "unmatched"
        finally:
            _cleanup(conn)
            conn.close()


class TestParseForecastRecords:
    def test_parses_infracost_json(self) -> None:
        breakdown = {
            "projects": [
                {
                    "breakdown": {
                        "resources": [
                            {
                                "name": "aws_instance.web_1",
                                "monthlyCost": "234.56",
                                "hourlyCost": "0.321",
                            }
                        ]
                    }
                }
            ]
        }
        records = _parse_forecast_records(breakdown)
        assert len(records) == 1
        assert records[0].resource_address == "aws_instance.web_1"
        assert records[0].monthly_cost == Decimal("234.56")
        assert records[0].currency == "USD"

    def test_empty_projects(self) -> None:
        records = _parse_forecast_records({"projects": []})
        assert records == []

    def test_missing_cost_defaults_zero(self) -> None:
        breakdown = {
            "projects": [
                {"breakdown": {"resources": [{"name": "aws_instance.ml_1"}]}}
            ]
        }
        records = _parse_forecast_records(breakdown)
        assert len(records) == 1
        assert records[0].monthly_cost == Decimal("0")
