"""Variance 계산 단위 테스트 — 예측/실제 비용 편차 로직."""

from datetime import UTC, datetime
from decimal import Decimal

import duckdb
import pytest

from dagster_project.assets.infracost_forecast import _parse_forecast_records


def _setup_duckdb_with_data(
    conn: duckdb.DuckDBPyConnection,
    forecast_rows: list[dict],
    actual_rows: list[dict],
) -> None:
    conn.execute("""
        CREATE TABLE dim_forecast (
            resource_address      VARCHAR NOT NULL,
            monthly_cost          DECIMAL(18,6) NOT NULL,
            hourly_cost           DECIMAL(18,6) NOT NULL,
            currency              VARCHAR NOT NULL,
            forecast_generated_at TIMESTAMPTZ NOT NULL
        )
    """)
    for r in forecast_rows:
        conn.execute(
            "INSERT INTO dim_forecast VALUES (?, ?, ?, ?, ?)",
            [
                r["resource_address"],
                r["monthly_cost"],
                r["hourly_cost"],
                r.get("currency", "USD"),
                r.get("forecast_generated_at", datetime.now(tz=UTC).isoformat()),
            ],
        )

    conn.execute("""
        CREATE TABLE fact_daily_cost (
            charge_date       DATE NOT NULL,
            resource_id       VARCHAR NOT NULL,
            resource_name     VARCHAR,
            resource_type     VARCHAR,
            service_name      VARCHAR,
            service_category  VARCHAR,
            region_id         VARCHAR,
            team              VARCHAR,
            product           VARCHAR,
            env               VARCHAR,
            cost_unit_key     VARCHAR,
            effective_cost    DECIMAL(18,6),
            billed_cost       DECIMAL(18,6),
            list_cost         DECIMAL(18,6),
            record_count      INTEGER
        )
    """)
    for r in actual_rows:
        conn.execute(
            "INSERT INTO fact_daily_cost VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                r["charge_date"],
                r["resource_id"],
                r.get("resource_name", r["resource_id"]),
                r.get("resource_type", "aws_instance"),
                r.get("service_name", "Amazon EC2"),
                r.get("service_category", "Compute"),
                r.get("region_id", "us-east-1"),
                r.get("team", "platform"),
                r.get("product", "checkout"),
                r.get("env", "prod"),
                r.get("cost_unit_key", "platform:checkout:prod"),
                r["effective_cost"],
                r["effective_cost"],
                r["effective_cost"],
                1,
            ],
        )


def _run_variance_query(
    conn: duckdb.DuckDBPyConnection,
    billing_month: str,
    over_pct: float = 20.0,
    under_pct: float = 20.0,
) -> list[dict]:
    from pathlib import Path

    sql = (
        (Path(__file__).parent.parent / "sql" / "marts" / "v_variance.sql")
        .read_text()
        .replace("{{variance_over_pct}}", str(over_pct))
        .replace("{{variance_under_pct}}", str(under_pct))
    )
    conn.execute(sql)
    rows = conn.execute(f"""
        SELECT resource_id, forecast_monthly, actual_mtd, variance_pct, status
        FROM v_variance
        WHERE billing_month = '{billing_month}' OR billing_month IS NULL
    """).fetchall()
    cols = ["resource_id", "forecast_monthly", "actual_mtd", "variance_pct", "status"]
    return [dict(zip(cols, row, strict=True)) for row in rows]


class TestVarianceStatus:
    def test_over_budget(self) -> None:
        conn = duckdb.connect(":memory:")
        _setup_duckdb_with_data(
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

    def test_under_budget(self) -> None:
        conn = duckdb.connect(":memory:")
        _setup_duckdb_with_data(
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

    def test_ok_within_threshold(self) -> None:
        conn = duckdb.connect(":memory:")
        _setup_duckdb_with_data(
            conn,
            forecast_rows=[{"resource_address": "aws_instance.ml_1", "monthly_cost": 100.0, "hourly_cost": 0.13}],
            actual_rows=[
                {"charge_date": "2024-01-15", "resource_id": "aws_instance.ml_1", "effective_cost": 110.0}
            ],
        )
        results = _run_variance_query(conn, "2024-01-01")
        assert len(results) == 1
        assert results[0]["status"] == "ok"

    def test_unmatched_no_actual(self) -> None:
        conn = duckdb.connect(":memory:")
        _setup_duckdb_with_data(
            conn,
            forecast_rows=[{"resource_address": "aws_db_instance.main_1", "monthly_cost": 500.0, "hourly_cost": 0.69}],
            actual_rows=[],
        )
        results = _run_variance_query(conn, "2024-01-01")
        assert len(results) == 1
        assert results[0]["status"] == "unmatched"

    def test_multiple_resources(self) -> None:
        conn = duckdb.connect(":memory:")
        _setup_duckdb_with_data(
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
