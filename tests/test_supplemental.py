"""보조 테스트 — 커버리지 70% 달성을 위한 추가 경로 검증."""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

from dagster_project.assets.infracost_forecast import _parse_forecast_records
from dagster_project.resources.duckdb_io import DuckDBResource
from dagster_project.resources.iceberg_catalog import IcebergCatalogResource


class TestParseForecastEdgeCases:
    def test_past_breakdown_fallback(self) -> None:
        breakdown = {
            "projects": [
                {
                    "pastBreakdown": {
                        "resources": [
                            {"name": "aws_instance.web_1", "monthlyCost": "100.0", "hourlyCost": "0.13"}
                        ]
                    }
                }
            ]
        }
        records = _parse_forecast_records(breakdown)
        assert len(records) == 1
        assert records[0].resource_address == "aws_instance.web_1"

    def test_invalid_cost_falls_back_to_zero(self) -> None:
        breakdown = {
            "projects": [
                {
                    "breakdown": {
                        "resources": [
                            {"name": "aws_instance.bad", "monthlyCost": "not-a-number", "hourlyCost": "also-bad"}
                        ]
                    }
                }
            ]
        }
        records = _parse_forecast_records(breakdown)
        assert len(records) == 1
        assert records[0].monthly_cost == Decimal("0")
        assert records[0].hourly_cost == Decimal("0")

    def test_resource_without_name_skipped(self) -> None:
        breakdown = {
            "projects": [
                {
                    "breakdown": {
                        "resources": [
                            {"name": "", "monthlyCost": "10.0"},
                            {"monthlyCost": "20.0"},
                        ]
                    }
                }
            ]
        }
        records = _parse_forecast_records(breakdown)
        assert records == []

    def test_monthly_usage_cost_fallback(self) -> None:
        breakdown = {
            "projects": [
                {
                    "breakdown": {
                        "resources": [
                            {"name": "aws_lambda_function.handler", "monthlyUsageCost": "5.5"}
                        ]
                    }
                }
            ]
        }
        records = _parse_forecast_records(breakdown)
        assert len(records) == 1
        assert records[0].monthly_cost == Decimal("5.5")


class TestDuckDBResource:
    def test_execute_runs_without_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.duckdb")
            resource = DuckDBResource(db_path=db_path)
            # execute는 연결을 닫고 반환하므로 예외 없이 완료되어야 함
            resource.execute("CREATE TABLE t (x INT)")
            resource.execute("INSERT INTO t VALUES (1)")

    def test_get_connection_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "subdir" / "test.duckdb")
            resource = DuckDBResource(db_path=db_path)
            with resource.get_connection() as conn:
                conn.execute("CREATE TABLE t (x INT)")
                conn.execute("INSERT INTO t VALUES (1)")
                result = conn.execute("SELECT x FROM t").fetchone()
                assert result is not None
                assert result[0] == 1


class TestIcebergCatalogResource:
    def test_ensure_namespace_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog = IcebergCatalogResource(
                warehouse_path=str(Path(tmpdir) / "warehouse"),
                catalog_db_path=str(Path(tmpdir) / "catalog.db"),
            )
            catalog.ensure_namespace("test_ns")
            catalog.ensure_namespace("test_ns")  # 두 번 호출해도 예외 없어야 함
