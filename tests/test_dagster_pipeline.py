"""Dagster pipeline process tests — end-to-end asset materialization.

Tests the full Dagster pipeline process: definitions loading, asset graph
resolution, full pipeline chain execution, and schedule/sensor registration.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import psycopg2
import pytest
from dagster import Definitions, materialize

from dagster_project.assets import (
    anomaly_detection,
    bronze_iceberg,
    bronze_iceberg_azure,
    bronze_iceberg_gcp,
    burn_rate,
    cost_trend,
    data_quality,
    fx_rates,
    gold_marts,
    gold_marts_azure,
    gold_marts_gcp,
    raw_cur,
    raw_cur_azure,
    raw_cur_gcp,
    resource_inventory,
    silver_focus,
    silver_focus_azure,
    silver_focus_gcp,
    tag_policy,
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
def full_resources(pipeline_tmpdir: Path):
    return {
        "iceberg_catalog": IcebergCatalogResource(
            warehouse_path=str(pipeline_tmpdir / "warehouse"),
            catalog_db_path=str(pipeline_tmpdir / "catalog.db"),
        ),
        "duckdb_resource": DuckDBResource(),
        "settings_store": SettingsStoreResource(),
        "budget_store": BudgetStoreResource(),
    }


# ───────────────────── Definitions structure ────────────────────────────

class TestDagsterDefinitions:
    def test_definitions_is_valid(self) -> None:
        from dagster_project.definitions import defs
        assert isinstance(defs, Definitions)

    def test_all_expected_assets_registered(self) -> None:
        from dagster_project.definitions import defs
        asset_graph = defs.resolve_asset_graph()
        keys = {str(k) for k in asset_graph.get_all_asset_keys()}
        expected = [
            "raw_cur", "raw_cur_gcp", "raw_cur_azure",
            "bronze_iceberg", "bronze_iceberg_gcp", "bronze_iceberg_azure",
            "silver_focus", "silver_focus_gcp", "silver_focus_azure",
            "gold_marts", "gold_marts_gcp", "gold_marts_azure",
            "anomaly_detection", "alert_dispatch",
            "prophet_forecast", "forecast_variance_prophet",
            "budget_alerts", "chargeback",
            "fx_rates", "cost_recommendations",
            "data_quality", "burn_rate",
            "resource_inventory", "tag_policy",
            "cost_allocation", "showback_report",
            "cost_trend", "savings_tracker",
            "budget_forecast", "tag_compliance_score",
        ]
        for name in expected:
            assert any(name in k for k in keys), f"Asset '{name}' not found in definitions"

    def test_sensors_registered(self) -> None:
        from dagster_project.definitions import defs
        sensor_names = [s.name for s in (defs.sensors or [])]
        assert "pipeline_run_success_sensor" in sensor_names
        assert "pipeline_run_failure_sensor" in sensor_names

    def test_schedules_registered(self) -> None:
        from dagster_project.definitions import defs
        schedule_names = [s.name for s in (defs.schedules or [])]
        assert "monthly_burn_rate_schedule" in schedule_names
        assert "daily_data_quality_schedule" in schedule_names

    def test_resources_registered(self) -> None:
        from dagster_project.definitions import defs
        resource_keys = set(defs.resources.keys()) if defs.resources else set()
        assert "iceberg_catalog" in resource_keys
        assert "duckdb_resource" in resource_keys
        assert "settings_store" in resource_keys
        assert "budget_store" in resource_keys


# ─────────── End-to-end pipeline chain (Raw → Bronze → Silver → Gold) ─────────

class TestFullPipelineChain:
    def test_aws_full_chain(self, full_resources: dict) -> None:
        """Raw → Bronze → Silver → Gold for AWS."""
        result = materialize(
            [
                raw_cur.raw_cur,
                bronze_iceberg.bronze_iceberg,
                silver_focus.silver_focus,
                gold_marts.gold_marts,
            ],
            partition_key="2024-03-01",
            resources=full_resources,
        )
        assert result.success
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM fact_daily_cost WHERE provider='aws' "
            "AND to_char(charge_date, 'YYYY-MM') = '2024-03'"
        )
        cnt = cur.fetchone()
        cur.close()
        conn.close()
        assert cnt is not None and cnt[0] > 0

    def test_gcp_full_chain(self, full_resources: dict) -> None:
        """Raw → Bronze → Silver → Gold for GCP."""
        result = materialize(
            [
                raw_cur_gcp.raw_cur_gcp,
                bronze_iceberg_gcp.bronze_iceberg_gcp,
                silver_focus_gcp.silver_focus_gcp,
                gold_marts_gcp.gold_marts_gcp,
            ],
            partition_key="2024-03-01",
            resources=full_resources,
        )
        assert result.success

    def test_azure_full_chain(self, full_resources: dict) -> None:
        """Raw → Bronze → Silver → Gold for Azure."""
        result = materialize(
            [
                raw_cur_azure.raw_cur_azure,
                bronze_iceberg_azure.bronze_iceberg_azure,
                silver_focus_azure.silver_focus_azure,
                gold_marts_azure.gold_marts_azure,
            ],
            partition_key="2024-03-01",
            resources=full_resources,
        )
        assert result.success


# ─────────── Analytics assets on seeded data ──────────────────────────

@pytest.fixture(scope="module")
def seeded_analytics_db():
    """Seed fact_daily_cost for analytics asset tests."""
    conn = _get_conn()
    cur = conn.cursor()
    prefix = "dptest_"
    cur.execute(f"DELETE FROM fact_daily_cost WHERE resource_id LIKE '{prefix}%'")
    for day in range(1, 20):
        cost = 8000.0 if day == 19 else 80.0
        cur.execute(
            "INSERT INTO fact_daily_cost (provider, charge_date, resource_id, resource_name, "
            "resource_type, service_name, service_category, region_id, team, product, env, "
            "cost_unit_key, effective_cost, billed_cost, list_cost, record_count) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                "aws", f"2024-03-{day:02d}",
                f"{prefix}aws_instance.web_1", "web_1", "aws_instance",
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
    cur.execute(f"DELETE FROM fact_daily_cost WHERE resource_id LIKE '{prefix}%'")
    cur.execute(f"DELETE FROM anomaly_scores WHERE resource_id LIKE '{prefix}%'")
    cur.close()
    conn.close()


class TestAnalyticsAssets:
    def test_anomaly_detection_process(self, seeded_analytics_db: None) -> None:
        result = materialize(
            [anomaly_detection.anomaly_detection],
            partition_key="2024-03-01",
            resources={
                "duckdb_resource": DuckDBResource(),
                "settings_store": SettingsStoreResource(),
            },
        )
        assert result.success

    def test_fx_rates_process(self) -> None:
        result = materialize(
            [fx_rates.fx_rates],
            partition_key="2024-03-01",
            resources={"duckdb_resource": DuckDBResource()},
        )
        assert result.success

    def test_data_quality_process(self) -> None:
        result = materialize(
            [data_quality.data_quality],
            resources={
                "duckdb_resource": DuckDBResource(),
                "settings_store": SettingsStoreResource(),
            },
        )
        assert result.success

    def test_burn_rate_process(self, seeded_analytics_db: None) -> None:
        result = materialize(
            [burn_rate.burn_rate],
            resources={
                "duckdb_resource": DuckDBResource(),
                "settings_store": SettingsStoreResource(),
                "budget_store": BudgetStoreResource(),
            },
        )
        assert result.success

    def test_resource_inventory_process(self, seeded_analytics_db: None) -> None:
        result = materialize(
            [resource_inventory.resource_inventory],
            resources={
                "duckdb_resource": DuckDBResource(),
                "settings_store": SettingsStoreResource(),
            },
        )
        assert result.success

    def test_tag_policy_process(self, seeded_analytics_db: None) -> None:
        result = materialize(
            [tag_policy.tag_policy],
            resources={
                "duckdb_resource": DuckDBResource(),
                "settings_store": SettingsStoreResource(),
            },
        )
        assert result.success

    def test_cost_trend_process(self, seeded_analytics_db: None) -> None:
        result = materialize(
            [cost_trend.cost_trend],
            resources={
                "duckdb_resource": DuckDBResource(),
                "settings_store": SettingsStoreResource(),
            },
        )
        assert result.success


# ─────────── Idempotency ─────────────────────────────────────────────

class TestIdempotency:
    def test_fx_rates_idempotent(self) -> None:
        """Running fx_rates twice should produce the same result."""
        resources = {"duckdb_resource": DuckDBResource()}
        r1 = materialize([fx_rates.fx_rates], partition_key="2024-03-01", resources=resources)
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM dim_fx_rates")
        count1 = cur.fetchone()[0]
        cur.close()
        conn.close()

        r2 = materialize([fx_rates.fx_rates], partition_key="2024-03-01", resources=resources)
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM dim_fx_rates")
        count2 = cur.fetchone()[0]
        cur.close()
        conn.close()

        assert r1.success and r2.success
        assert count1 == count2

    def test_gold_marts_idempotent(self, full_resources: dict) -> None:
        """Running gold_marts twice for the same partition should not duplicate rows."""
        assets = [
            raw_cur.raw_cur,
            bronze_iceberg.bronze_iceberg,
            silver_focus.silver_focus,
            gold_marts.gold_marts,
        ]
        r1 = materialize(assets, partition_key="2024-04-01", resources=full_resources)
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM fact_daily_cost WHERE provider='aws' "
            "AND to_char(charge_date, 'YYYY-MM') = '2024-04'"
        )
        count1 = cur.fetchone()[0]
        cur.close()
        conn.close()

        r2 = materialize(assets, partition_key="2024-04-01", resources=full_resources)
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM fact_daily_cost WHERE provider='aws' "
            "AND to_char(charge_date, 'YYYY-MM') = '2024-04'"
        )
        count2 = cur.fetchone()[0]
        cur.close()
        conn.close()

        assert r1.success and r2.success
        assert count1 == count2
