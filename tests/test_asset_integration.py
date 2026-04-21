"""Asset 통합 테스트 — Dagster materialize를 통한 asset 실행 커버리지.

PostgreSQL(finops DB)에 직접 연결하여 테스트한다.
테스트 데이터는 실제 테이블에 삽입되며, fixture에서 정리한다.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import polars as pl
import psycopg2
import pytest
from dagster import materialize

from dagster_project.assets import (
    alert_dispatch,
    anomaly_detection,
    bronze_iceberg,
    bronze_iceberg_azure,
    bronze_iceberg_gcp,
    budget_alerts,
    chargeback,
    forecast_variance_prophet,
    fx_rates,
    gold_marts,
    gold_marts_azure,
    gold_marts_gcp,
    prophet_forecast,
    raw_cur,
    raw_cur_azure,
    raw_cur_gcp,
    silver_focus,
    silver_focus_azure,
    silver_focus_gcp,
    variance,
)
from dagster_project.config import load_config
from dagster_project.resources.budget_store import BudgetStoreResource
from dagster_project.resources.duckdb_io import DuckDBResource
from dagster_project.resources.iceberg_catalog import IcebergCatalogResource
from dagster_project.resources.settings_store import SettingsStoreResource

_cfg = load_config()


def _get_conn() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(_cfg.postgres.dsn)
    conn.autocommit = True
    return conn


@pytest.fixture(scope="module")
def pipeline_tmpdir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="module")
def pipeline_resources(pipeline_tmpdir: Path):
    warehouse = str(pipeline_tmpdir / "warehouse")
    catalog_db = str(pipeline_tmpdir / "catalog.db")
    return {
        "iceberg_catalog": IcebergCatalogResource(
            warehouse_path=warehouse,
            catalog_db_path=catalog_db,
        ),
        "duckdb_resource": DuckDBResource(),
        "settings_store": SettingsStoreResource(),
        "budget_store": BudgetStoreResource(),
    }


# ───────────────────────────────────── Raw CUR ─────────────────────────────────────

class TestRawCurAssets:
    def test_raw_cur_aws_success(self) -> None:
        result = materialize([raw_cur.raw_cur], partition_key="2024-01-01")
        assert result.success
        records = result.output_for_node("raw_cur")
        assert len(records) > 0

    def test_raw_cur_gcp_success(self) -> None:
        result = materialize([raw_cur_gcp.raw_cur_gcp], partition_key="2024-01-01")
        assert result.success
        records = result.output_for_node("raw_cur_gcp")
        assert len(records) > 0

    def test_raw_cur_azure_success(self) -> None:
        result = materialize([raw_cur_azure.raw_cur_azure], partition_key="2024-01-01")
        assert result.success
        records = result.output_for_node("raw_cur_azure")
        assert len(records) > 0

    def test_raw_cur_december_partition(self) -> None:
        result = materialize([raw_cur.raw_cur], partition_key="2024-12-01")
        assert result.success
        records = result.output_for_node("raw_cur")
        assert len(records) > 0

    def test_raw_cur_different_partitions_different_counts(self) -> None:
        result_jan = materialize([raw_cur.raw_cur], partition_key="2024-01-01")
        result_feb = materialize([raw_cur.raw_cur], partition_key="2024-02-01")
        jan = result_jan.output_for_node("raw_cur")
        feb = result_feb.output_for_node("raw_cur")
        assert len(jan) != len(feb)


# ──────────────────────── Bronze → Silver → Gold pipeline ──────────────────────────

class TestBronzePipeline:
    def test_aws_bronze_iceberg(self, pipeline_resources: dict) -> None:
        result = materialize(
            [raw_cur.raw_cur, bronze_iceberg.bronze_iceberg],
            partition_key="2024-01-01",
            resources=pipeline_resources,
        )
        assert result.success

    def test_gcp_bronze_iceberg(self, pipeline_resources: dict) -> None:
        result = materialize(
            [raw_cur_gcp.raw_cur_gcp, bronze_iceberg_gcp.bronze_iceberg_gcp],
            partition_key="2024-01-01",
            resources=pipeline_resources,
        )
        assert result.success

    def test_azure_bronze_iceberg(self, pipeline_resources: dict) -> None:
        result = materialize(
            [raw_cur_azure.raw_cur_azure, bronze_iceberg_azure.bronze_iceberg_azure],
            partition_key="2024-01-01",
            resources=pipeline_resources,
        )
        assert result.success


class TestSilverPipeline:
    def test_aws_silver_focus(self, pipeline_resources: dict) -> None:
        result = materialize(
            [
                raw_cur.raw_cur,
                bronze_iceberg.bronze_iceberg,
                silver_focus.silver_focus,
            ],
            partition_key="2024-01-01",
            resources=pipeline_resources,
        )
        assert result.success

    def test_gcp_silver_focus(self, pipeline_resources: dict) -> None:
        result = materialize(
            [
                raw_cur_gcp.raw_cur_gcp,
                bronze_iceberg_gcp.bronze_iceberg_gcp,
                silver_focus_gcp.silver_focus_gcp,
            ],
            partition_key="2024-01-01",
            resources=pipeline_resources,
        )
        assert result.success

    def test_azure_silver_focus(self, pipeline_resources: dict) -> None:
        result = materialize(
            [
                raw_cur_azure.raw_cur_azure,
                bronze_iceberg_azure.bronze_iceberg_azure,
                silver_focus_azure.silver_focus_azure,
            ],
            partition_key="2024-01-01",
            resources=pipeline_resources,
        )
        assert result.success


class TestGoldMartsPipeline:
    def test_aws_gold_marts(self, pipeline_resources: dict) -> None:
        result = materialize(
            [
                raw_cur.raw_cur,
                bronze_iceberg.bronze_iceberg,
                silver_focus.silver_focus,
                gold_marts.gold_marts,
            ],
            partition_key="2024-01-01",
            resources=pipeline_resources,
        )
        assert result.success
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM fact_daily_cost WHERE provider='aws'")
        cnt = cur.fetchone()
        cur.close()
        conn.close()
        assert cnt is not None and cnt[0] > 0

    def test_gcp_gold_marts(self, pipeline_resources: dict) -> None:
        result = materialize(
            [
                raw_cur_gcp.raw_cur_gcp,
                bronze_iceberg_gcp.bronze_iceberg_gcp,
                silver_focus_gcp.silver_focus_gcp,
                gold_marts_gcp.gold_marts_gcp,
            ],
            partition_key="2024-01-01",
            resources=pipeline_resources,
        )
        assert result.success

    def test_azure_gold_marts(self, pipeline_resources: dict) -> None:
        result = materialize(
            [
                raw_cur_azure.raw_cur_azure,
                bronze_iceberg_azure.bronze_iceberg_azure,
                silver_focus_azure.silver_focus_azure,
                gold_marts_azure.gold_marts_azure,
            ],
            partition_key="2024-01-01",
            resources=pipeline_resources,
        )
        assert result.success


# ───────────────────────── Analytics / Reporting ────────────────────────────────────

@pytest.fixture(scope="module")
def seeded_db():
    """fact_daily_cost에 테스트 데이터가 채워진 상태를 보장한다."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM fact_daily_cost WHERE resource_id = 'inttest_aws_instance.web_1'")
    for day in range(1, 15):
        cost = 10000.0 if day == 14 else 100.0
        cur.execute(
            "INSERT INTO fact_daily_cost (provider, charge_date, resource_id, resource_name, "
            "resource_type, service_name, service_category, region_id, team, product, env, "
            "cost_unit_key, effective_cost, billed_cost, list_cost, record_count) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                "aws", f"2024-01-{day:02d}",
                "inttest_aws_instance.web_1", "web_1", "aws_instance",
                "EC2", "Compute", "us-east-1",
                "platform", "web", "prod", "platform:web:prod",
                cost, cost, cost * 1.1, 1,
            ],
        )
    cur.close()
    conn.close()
    yield
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM fact_daily_cost WHERE resource_id = 'inttest_aws_instance.web_1'")
    cur.execute("DELETE FROM anomaly_scores WHERE resource_id = 'inttest_aws_instance.web_1'")
    cur.close()
    conn.close()


class TestAnomalyDetectionAsset:
    def test_anomaly_detection_runs(self, seeded_db: None) -> None:
        result = materialize(
            [anomaly_detection.anomaly_detection],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(),
                "settings_store": SettingsStoreResource(),
            },
        )
        assert result.success

    def test_anomaly_detection_creates_anomaly_scores(self, seeded_db: None) -> None:
        materialize(
            [anomaly_detection.anomaly_detection],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(),
                "settings_store": SettingsStoreResource(),
            },
        )
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='anomaly_scores'"
        )
        tables = cur.fetchall()
        cur.close()
        conn.close()
        assert len(tables) == 1


class TestAlertDispatchAsset:
    def test_alert_dispatch_runs(self) -> None:
        result = materialize(
            [alert_dispatch.alert_dispatch],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(),
                "settings_store": SettingsStoreResource(),
            },
        )
        assert result.success


class TestVarianceAsset:
    def test_variance_runs(self) -> None:
        result = materialize(
            [variance.variance],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(),
                "settings_store": SettingsStoreResource(),
            },
        )
        assert result.success


class TestProphetForecastAsset:
    def test_prophet_forecast_runs(self) -> None:
        result = materialize(
            [prophet_forecast.prophet_forecast],
            partition_key="2024-01-01",
            resources={"duckdb_resource": DuckDBResource()},
        )
        assert result.success


class TestForecastVarianceProphetAsset:
    def test_forecast_variance_prophet_runs(self) -> None:
        result = materialize(
            [forecast_variance_prophet.forecast_variance_prophet],
            partition_key="2024-01-01",
            resources={"duckdb_resource": DuckDBResource()},
        )
        assert result.success


class TestBudgetAlertsAsset:
    def test_budget_alerts_runs(self) -> None:
        result = materialize(
            [budget_alerts.budget_alerts],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(),
                "budget_store": BudgetStoreResource(),
                "settings_store": SettingsStoreResource(),
            },
        )
        assert result.success


class TestChargebackAsset:
    def test_chargeback_runs(self) -> None:
        result = materialize(
            [chargeback.chargeback],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(),
                "budget_store": BudgetStoreResource(),
            },
        )
        assert result.success


class TestFxRatesAsset:
    def test_fx_rates_runs(self) -> None:
        result = materialize(
            [fx_rates.fx_rates],
            partition_key="2024-01-01",
            resources={"duckdb_resource": DuckDBResource()},
        )
        assert result.success

    def test_fx_rates_idempotent(self) -> None:
        resources = {"duckdb_resource": DuckDBResource()}
        result1 = materialize([fx_rates.fx_rates], partition_key="2024-01-01", resources=resources)
        result2 = materialize([fx_rates.fx_rates], partition_key="2024-01-01", resources=resources)
        assert result1.success
        assert result2.success
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM dim_fx_rates")
        cnt = cur.fetchone()
        cur.close()
        conn.close()
        assert cnt is not None and cnt[0] > 0
