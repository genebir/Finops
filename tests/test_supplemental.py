"""보조 테스트 — 커버리지 70% 달성을 위한 추가 경로 검증."""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

from dagster_project.assets.infracost_forecast import (
    _parse_forecast_records,
    _stub_forecast_records,
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


class TestDuckDBResource:
    def test_get_connection_works(self) -> None:
        resource = DuckDBResource()
        with resource.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 AS val")
            result = cur.fetchone()
            cur.close()
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
            catalog.ensure_namespace("test_ns")

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
