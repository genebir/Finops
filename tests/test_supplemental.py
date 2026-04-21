"""보조 테스트 — 커버리지 70% 달성을 위한 추가 경로 검증."""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

from dagster_project.assets.infracost_forecast import (
    _parse_forecast_records,
    _stub_forecast_records,
    _write_forecast_rows,
)
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


class TestWriteForecastRows:
    def test_write_forecast_rows_creates_table(self) -> None:
        import duckdb
        conn = duckdb.connect()
        rows = [
            {
                "resource_address": "aws_instance.web_1",
                "monthly_cost": "100.0",
                "hourly_cost": "0.14",
                "currency": "USD",
                "forecast_generated_at": "2024-01-01T00:00:00+00:00",
            }
        ]
        _write_forecast_rows(conn, rows)
        result = conn.execute("SELECT COUNT(*) FROM dim_forecast").fetchone()
        assert result is not None
        assert result[0] == 1

    def test_write_forecast_rows_empty_creates_empty_table(self) -> None:
        import duckdb
        conn = duckdb.connect()
        _write_forecast_rows(conn, [])
        result = conn.execute("SELECT COUNT(*) FROM dim_forecast").fetchone()
        assert result is not None
        assert result[0] == 0


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


class TestStubForecastRecords:
    def test_stub_returns_nonempty_list(self) -> None:
        records = _stub_forecast_records()
        assert len(records) > 0

    def test_stub_has_positive_monthly_cost(self) -> None:
        records = _stub_forecast_records()
        for rec in records:
            assert rec.monthly_cost > Decimal("0")
            assert rec.hourly_cost > Decimal("0")
            assert rec.currency == "USD"

    def test_stub_resource_ids_match_terraform(self) -> None:
        from dagster_project.generators.aws_cur_generator import _TERRAFORM_RESOURCES
        records = _stub_forecast_records()
        record_addresses = {r.resource_address for r in records}
        for res in _TERRAFORM_RESOURCES:
            assert res.resource_id in record_addresses


class TestIcebergCatalogResource:
    def test_ensure_namespace_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog = IcebergCatalogResource(
                warehouse_path=str(Path(tmpdir) / "warehouse"),
                catalog_db_path=str(Path(tmpdir) / "catalog.db"),
            )
            catalog.ensure_namespace("test_ns")
            catalog.ensure_namespace("test_ns")  # 두 번 호출해도 예외 없어야 함

    def test_ensure_table_with_properties(self) -> None:
        """properties 파라미터 경로 커버."""
        from pyiceberg.schema import Schema
        from pyiceberg.types import NestedField, StringType

        with tempfile.TemporaryDirectory() as tmpdir:
            catalog = IcebergCatalogResource(
                warehouse_path=str(Path(tmpdir) / "warehouse"),
                catalog_db_path=str(Path(tmpdir) / "catalog.db"),
            )
            schema = Schema(NestedField(1, "name", StringType(), required=False))
            table = catalog.ensure_table(
                "test_ns.test_table",
                schema=schema,
                properties={"write.format.default": "parquet"},
            )
            assert table is not None
