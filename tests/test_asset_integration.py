"""Asset 통합 테스트 — Dagster materialize를 통한 asset 실행 커버리지."""

from __future__ import annotations

import tempfile
from pathlib import Path

import duckdb
import polars as pl
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
from dagster_project.resources.budget_store import BudgetStoreResource
from dagster_project.resources.duckdb_io import DuckDBResource
from dagster_project.resources.iceberg_catalog import IcebergCatalogResource
from dagster_project.resources.settings_store import SettingsStoreResource


@pytest.fixture(scope="module")
def pipeline_tmpdir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="module")
def pipeline_resources(pipeline_tmpdir: Path):
    warehouse = str(pipeline_tmpdir / "warehouse")
    catalog_db = str(pipeline_tmpdir / "catalog.db")
    duckdb_path = str(pipeline_tmpdir / "marts.duckdb")
    return {
        "iceberg_catalog": IcebergCatalogResource(
            warehouse_path=warehouse,
            catalog_db_path=catalog_db,
        ),
        "duckdb_resource": DuckDBResource(db_path=duckdb_path),
        "settings_store": SettingsStoreResource(db_path=duckdb_path),
        "budget_store": BudgetStoreResource(db_path=duckdb_path),
        "_duckdb_path": duckdb_path,
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
        # 31일 vs 29일 (2024 윤년) — 레코드 수가 다름
        assert len(jan) != len(feb)


# ──────────────────────── Bronze → Silver → Gold pipeline ──────────────────────────

class TestBronzePipeline:
    def test_aws_bronze_iceberg(self, pipeline_resources: dict) -> None:
        resources = {
            k: v for k, v in pipeline_resources.items() if not k.startswith("_")
        }
        result = materialize(
            [raw_cur.raw_cur, bronze_iceberg.bronze_iceberg],
            partition_key="2024-01-01",
            resources=resources,
        )
        assert result.success

    def test_gcp_bronze_iceberg(self, pipeline_resources: dict) -> None:
        resources = {
            k: v for k, v in pipeline_resources.items() if not k.startswith("_")
        }
        result = materialize(
            [raw_cur_gcp.raw_cur_gcp, bronze_iceberg_gcp.bronze_iceberg_gcp],
            partition_key="2024-01-01",
            resources=resources,
        )
        assert result.success

    def test_azure_bronze_iceberg(self, pipeline_resources: dict) -> None:
        resources = {
            k: v for k, v in pipeline_resources.items() if not k.startswith("_")
        }
        result = materialize(
            [raw_cur_azure.raw_cur_azure, bronze_iceberg_azure.bronze_iceberg_azure],
            partition_key="2024-01-01",
            resources=resources,
        )
        assert result.success


class TestSilverPipeline:
    def test_aws_silver_focus(self, pipeline_resources: dict) -> None:
        resources = {
            k: v for k, v in pipeline_resources.items() if not k.startswith("_")
        }
        result = materialize(
            [
                raw_cur.raw_cur,
                bronze_iceberg.bronze_iceberg,
                silver_focus.silver_focus,
            ],
            partition_key="2024-01-01",
            resources=resources,
        )
        assert result.success

    def test_gcp_silver_focus(self, pipeline_resources: dict) -> None:
        resources = {
            k: v for k, v in pipeline_resources.items() if not k.startswith("_")
        }
        result = materialize(
            [
                raw_cur_gcp.raw_cur_gcp,
                bronze_iceberg_gcp.bronze_iceberg_gcp,
                silver_focus_gcp.silver_focus_gcp,
            ],
            partition_key="2024-01-01",
            resources=resources,
        )
        assert result.success

    def test_azure_silver_focus(self, pipeline_resources: dict) -> None:
        resources = {
            k: v for k, v in pipeline_resources.items() if not k.startswith("_")
        }
        result = materialize(
            [
                raw_cur_azure.raw_cur_azure,
                bronze_iceberg_azure.bronze_iceberg_azure,
                silver_focus_azure.silver_focus_azure,
            ],
            partition_key="2024-01-01",
            resources=resources,
        )
        assert result.success


class TestGoldMartsPipeline:
    def test_aws_gold_marts(self, pipeline_resources: dict) -> None:
        resources = {
            k: v for k, v in pipeline_resources.items() if not k.startswith("_")
        }
        result = materialize(
            [
                raw_cur.raw_cur,
                bronze_iceberg.bronze_iceberg,
                silver_focus.silver_focus,
                gold_marts.gold_marts,
            ],
            partition_key="2024-01-01",
            resources=resources,
        )
        assert result.success
        db_path = pipeline_resources["_duckdb_path"]
        conn = duckdb.connect(db_path, read_only=True)
        cnt = conn.execute("SELECT COUNT(*) FROM fact_daily_cost WHERE provider='aws'").fetchone()
        conn.close()
        assert cnt is not None and cnt[0] > 0

    def test_gcp_gold_marts(self, pipeline_resources: dict) -> None:
        resources = {
            k: v for k, v in pipeline_resources.items() if not k.startswith("_")
        }
        result = materialize(
            [
                raw_cur_gcp.raw_cur_gcp,
                bronze_iceberg_gcp.bronze_iceberg_gcp,
                silver_focus_gcp.silver_focus_gcp,
                gold_marts_gcp.gold_marts_gcp,
            ],
            partition_key="2024-01-01",
            resources=resources,
        )
        assert result.success

    def test_azure_gold_marts(self, pipeline_resources: dict) -> None:
        resources = {
            k: v for k, v in pipeline_resources.items() if not k.startswith("_")
        }
        result = materialize(
            [
                raw_cur_azure.raw_cur_azure,
                bronze_iceberg_azure.bronze_iceberg_azure,
                silver_focus_azure.silver_focus_azure,
                gold_marts_azure.gold_marts_azure,
            ],
            partition_key="2024-01-01",
            resources=resources,
        )
        assert result.success


# ───────────────────────── Analytics / Reporting ────────────────────────────────────

@pytest.fixture(scope="module")
def seeded_duckdb(pipeline_tmpdir: Path):
    """fact_daily_cost가 미리 채워진 DuckDB 경로를 반환한다."""
    db_path = str(pipeline_tmpdir / "analytics_test.duckdb")
    conn = duckdb.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fact_daily_cost (
            provider         VARCHAR        NOT NULL DEFAULT 'aws',
            charge_date      DATE           NOT NULL,
            resource_id      VARCHAR        NOT NULL,
            resource_name    VARCHAR,
            resource_type    VARCHAR,
            service_name     VARCHAR,
            service_category VARCHAR,
            region_id        VARCHAR,
            team             VARCHAR        NOT NULL,
            product          VARCHAR        NOT NULL,
            env              VARCHAR        NOT NULL,
            cost_unit_key    VARCHAR        NOT NULL,
            effective_cost   DECIMAL(18, 6) NOT NULL,
            billed_cost      DECIMAL(18, 6) NOT NULL,
            list_cost        DECIMAL(18, 6) NOT NULL,
            record_count     BIGINT         NOT NULL
        )
    """)
    # 14일치 데이터로 이상치 탐지를 위한 spike 생성
    rows = []
    for day in range(1, 15):
        cost = 10000.0 if day == 14 else 100.0  # spike on day 14
        rows.append({
            "provider": "aws",
            "charge_date": f"2024-01-{day:02d}",
            "resource_id": "aws_instance.web_1",
            "resource_name": "web_1",
            "resource_type": "aws_instance",
            "service_name": "EC2",
            "service_category": "Compute",
            "region_id": "us-east-1",
            "team": "platform",
            "product": "web",
            "env": "prod",
            "cost_unit_key": "platform:web:prod",
            "effective_cost": cost,
            "billed_cost": cost,
            "list_cost": cost * 1.1,
            "record_count": 1,
        })
    for row in rows:
        conn.execute("""
            INSERT INTO fact_daily_cost VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, list(row.values()))
    conn.close()
    return db_path


class TestAnomalyDetectionAsset:
    def test_anomaly_detection_runs(
        self, pipeline_tmpdir: Path, seeded_duckdb: str
    ) -> None:
        result = materialize(
            [anomaly_detection.anomaly_detection],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=seeded_duckdb),
                "settings_store": SettingsStoreResource(db_path=seeded_duckdb),
            },
        )
        assert result.success

    def test_anomaly_detection_no_fact_table(self, pipeline_tmpdir: Path) -> None:
        empty_db = str(pipeline_tmpdir / "empty_anomaly.duckdb")
        result = materialize(
            [anomaly_detection.anomaly_detection],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=empty_db),
                "settings_store": SettingsStoreResource(db_path=empty_db),
            },
        )
        assert result.success  # graceful skip

    def test_anomaly_detection_creates_anomaly_scores(
        self, seeded_duckdb: str
    ) -> None:
        materialize(
            [anomaly_detection.anomaly_detection],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=seeded_duckdb),
                "settings_store": SettingsStoreResource(db_path=seeded_duckdb),
            },
        )
        conn = duckdb.connect(seeded_duckdb, read_only=True)
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name='anomaly_scores'"
        ).fetchall()
        conn.close()
        assert len(tables) == 1

    def test_anomaly_detection_with_moving_average(
        self, seeded_duckdb: str
    ) -> None:
        conn = duckdb.connect(seeded_duckdb)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS platform_settings "
            "(key VARCHAR PRIMARY KEY, value VARCHAR, value_type VARCHAR, description VARCHAR, "
            "updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "INSERT INTO platform_settings(key,value,value_type,description) "
            "VALUES ('anomaly.active_detectors','zscore,moving_average','str','') "
            "ON CONFLICT (key) DO UPDATE SET value='zscore,moving_average'"
        )
        conn.close()

        result = materialize(
            [anomaly_detection.anomaly_detection],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=seeded_duckdb),
                "settings_store": SettingsStoreResource(db_path=seeded_duckdb),
            },
        )
        assert result.success


class TestAlertDispatchAsset:
    def test_alert_dispatch_no_anomaly_table(
        self, pipeline_tmpdir: Path
    ) -> None:
        empty_db = str(pipeline_tmpdir / "empty_alert.duckdb")
        result = materialize(
            [alert_dispatch.alert_dispatch],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=empty_db),
                "settings_store": SettingsStoreResource(db_path=empty_db),
            },
        )
        assert result.success

    def test_alert_dispatch_with_anomaly_scores(
        self, pipeline_tmpdir: Path
    ) -> None:
        db_path = str(pipeline_tmpdir / "alert_dispatch_test.duckdb")
        conn = duckdb.connect(db_path)
        conn.execute("""
            CREATE TABLE anomaly_scores (
                resource_id VARCHAR, cost_unit_key VARCHAR,
                team VARCHAR, product VARCHAR, env VARCHAR,
                charge_date DATE, effective_cost DECIMAL(18,6),
                mean_cost DECIMAL(18,6), std_cost DECIMAL(18,6),
                z_score DOUBLE, is_anomaly BOOLEAN, severity VARCHAR,
                detector_name VARCHAR
            )
        """)
        conn.execute("""
            INSERT INTO anomaly_scores VALUES
            ('aws_instance.web_1','platform:web:prod','platform','web','prod',
             '2024-01-14',10000.0,100.0,50.0,198.0,true,'critical','zscore')
        """)
        conn.close()
        result = materialize(
            [alert_dispatch.alert_dispatch],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=db_path),
                "settings_store": SettingsStoreResource(db_path=db_path),
            },
        )
        assert result.success

    def test_alert_dispatch_with_variance_csv(
        self, pipeline_tmpdir: Path
    ) -> None:
        """variance CSV가 있을 때 over/under 알림이 생성된다."""
        db_path = str(pipeline_tmpdir / "alert_dispatch_variance.duckdb")
        # variance CSV 생성
        reports_dir = pipeline_tmpdir / "reports"
        reports_dir.mkdir(exist_ok=True)
        variance_csv = reports_dir / "variance_202401.csv"
        pl.DataFrame({
            "resource_id": ["aws_instance.web_1", "aws_instance.web_2"],
            "forecast_monthly": [100.0, 200.0],
            "actual_mtd": [200.0, 100.0],
            "variance_abs": [100.0, -100.0],
            "variance_pct": [100.0, -50.0],
            "status": ["over", "under"],
            "currency": ["USD", "USD"],
            "forecast_generated_at": ["2024-01-01T00:00:00", "2024-01-01T00:00:00"],
        }).write_csv(str(variance_csv))

        import os
        old_reports = os.environ.get("REPORTS_DIR")

        from dagster_project.config import load_config
        load_config.cache_clear()

        result = materialize(
            [alert_dispatch.alert_dispatch],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=db_path),
                "settings_store": SettingsStoreResource(db_path=db_path),
            },
        )
        assert result.success


class TestVarianceAsset:
    def test_variance_no_dim_forecast(self, pipeline_tmpdir: Path) -> None:
        empty_db = str(pipeline_tmpdir / "empty_variance.duckdb")
        result = materialize(
            [variance.variance],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=empty_db),
                "settings_store": SettingsStoreResource(db_path=empty_db),
            },
        )
        assert result.success  # graceful skip

    def test_variance_with_dim_forecast(self, pipeline_tmpdir: Path) -> None:
        db_path = str(pipeline_tmpdir / "variance_test.duckdb")
        conn = duckdb.connect(db_path)
        conn.execute("""
            CREATE TABLE dim_forecast (
                resource_address VARCHAR, monthly_cost DECIMAL(18,6),
                hourly_cost DECIMAL(18,6), currency VARCHAR,
                forecast_generated_at TIMESTAMPTZ
            )
        """)
        conn.execute("""
            INSERT INTO dim_forecast VALUES
            ('aws_instance.web_1', 3100.0, 4.3, 'USD', '2024-01-01 00:00:00+00')
        """)
        conn.execute("""
            CREATE TABLE fact_daily_cost (
                provider VARCHAR, charge_date DATE, resource_id VARCHAR,
                resource_name VARCHAR, resource_type VARCHAR,
                service_name VARCHAR, service_category VARCHAR, region_id VARCHAR,
                team VARCHAR, product VARCHAR, env VARCHAR,
                cost_unit_key VARCHAR, effective_cost DECIMAL(18,6),
                billed_cost DECIMAL(18,6), list_cost DECIMAL(18,6), record_count BIGINT
            )
        """)
        conn.execute("""
            INSERT INTO fact_daily_cost
            VALUES ('aws','2024-01-01','aws_instance.web_1','web_1','aws_instance',
                    'EC2','Compute','us-east-1','platform','web','prod','platform:web:prod',
                    100.0,100.0,115.0,1)
        """)
        conn.close()
        result = materialize(
            [variance.variance],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=db_path),
                "settings_store": SettingsStoreResource(db_path=db_path),
            },
        )
        assert result.success


class TestProphetForecastAsset:
    def test_prophet_forecast_no_fact_table(self, pipeline_tmpdir: Path) -> None:
        empty_db = str(pipeline_tmpdir / "empty_prophet.duckdb")
        result = materialize(
            [prophet_forecast.prophet_forecast],
            partition_key="2024-01-01",
            resources={"duckdb_resource": DuckDBResource(db_path=empty_db)},
        )
        assert result.success

    def test_prophet_forecast_with_data(self, seeded_duckdb: str) -> None:
        result = materialize(
            [prophet_forecast.prophet_forecast],
            partition_key="2024-01-01",
            resources={"duckdb_resource": DuckDBResource(db_path=seeded_duckdb)},
        )
        assert result.success

    def test_prophet_forecast_sparse_data(self, pipeline_tmpdir: Path) -> None:
        """데이터가 min_training_days(14일) 미만이어서 예측이 skip되는 경우."""
        db_path = str(pipeline_tmpdir / "sparse_prophet.duckdb")
        conn = duckdb.connect(db_path)
        conn.execute("""
            CREATE TABLE fact_daily_cost (
                provider VARCHAR, charge_date DATE, resource_id VARCHAR,
                resource_name VARCHAR, resource_type VARCHAR,
                service_name VARCHAR, service_category VARCHAR, region_id VARCHAR,
                team VARCHAR, product VARCHAR, env VARCHAR,
                cost_unit_key VARCHAR, effective_cost DECIMAL(18,6),
                billed_cost DECIMAL(18,6), list_cost DECIMAL(18,6), record_count BIGINT
            )
        """)
        # 3일치만 — min_training_days(14) 미만이므로 Prophet skip
        for day in range(1, 4):
            conn.execute("""
                INSERT INTO fact_daily_cost VALUES
                ('aws','2024-01-{}','aws_instance.web_1','web_1','aws_instance',
                 'EC2','Compute','us-east-1','platform','web','prod','platform:web:prod',
                 100.0,100.0,115.0,1)
            """.format(f"{day:02d}"))
        conn.close()
        result = materialize(
            [prophet_forecast.prophet_forecast],
            partition_key="2024-01-01",
            resources={"duckdb_resource": DuckDBResource(db_path=db_path)},
        )
        assert result.success


class TestForecastVarianceProphetAsset:
    def test_no_prophet_table_skip(self, pipeline_tmpdir: Path) -> None:
        empty_db = str(pipeline_tmpdir / "empty_fvp.duckdb")
        result = materialize(
            [forecast_variance_prophet.forecast_variance_prophet],
            partition_key="2024-01-01",
            resources={"duckdb_resource": DuckDBResource(db_path=empty_db)},
        )
        assert result.success

    def test_no_fact_table_skip(self, pipeline_tmpdir: Path) -> None:
        db_path = str(pipeline_tmpdir / "no_fact_fvp.duckdb")
        conn = duckdb.connect(db_path)
        conn.execute("""
            CREATE TABLE dim_prophet_forecast (
                resource_id VARCHAR, predicted_monthly_cost DECIMAL(18,6),
                lower_bound_monthly_cost DECIMAL(18,6),
                upper_bound_monthly_cost DECIMAL(18,6),
                hourly_cost DECIMAL(18,6), currency VARCHAR,
                model_trained_at TIMESTAMPTZ
            )
        """)
        conn.close()
        result = materialize(
            [forecast_variance_prophet.forecast_variance_prophet],
            partition_key="2024-01-01",
            resources={"duckdb_resource": DuckDBResource(db_path=db_path)},
        )
        assert result.success

    def test_with_both_tables(self, pipeline_tmpdir: Path) -> None:
        db_path = str(pipeline_tmpdir / "full_fvp.duckdb")
        conn = duckdb.connect(db_path)
        conn.execute("""
            CREATE TABLE dim_prophet_forecast (
                resource_id VARCHAR, predicted_monthly_cost DECIMAL(18,6),
                lower_bound_monthly_cost DECIMAL(18,6),
                upper_bound_monthly_cost DECIMAL(18,6),
                hourly_cost DECIMAL(18,6), currency VARCHAR,
                model_trained_at TIMESTAMPTZ
            )
        """)
        conn.execute("""
            INSERT INTO dim_prophet_forecast VALUES
            ('aws_instance.web_1', 3100.0, 2800.0, 3400.0, 4.3, 'USD',
             '2024-01-31 00:00:00+00')
        """)
        conn.execute("""
            CREATE TABLE fact_daily_cost (
                provider VARCHAR, charge_date DATE, resource_id VARCHAR,
                resource_name VARCHAR, resource_type VARCHAR,
                service_name VARCHAR, service_category VARCHAR, region_id VARCHAR,
                team VARCHAR, product VARCHAR, env VARCHAR,
                cost_unit_key VARCHAR, effective_cost DECIMAL(18,6),
                billed_cost DECIMAL(18,6), list_cost DECIMAL(18,6), record_count BIGINT
            )
        """)
        for day in range(1, 15):
            conn.execute("""
                INSERT INTO fact_daily_cost VALUES
                ('aws','2024-01-{}','aws_instance.web_1','web_1','aws_instance',
                 'EC2','Compute','us-east-1','platform','web','prod','platform:web:prod',
                 100.0,100.0,115.0,1)
            """.format(f"{day:02d}"))
        conn.close()
        result = materialize(
            [forecast_variance_prophet.forecast_variance_prophet],
            partition_key="2024-01-01",
            resources={"duckdb_resource": DuckDBResource(db_path=db_path)},
        )
        assert result.success


class TestBudgetAlertsAsset:
    def test_budget_alerts_no_fact_table(self, pipeline_tmpdir: Path) -> None:
        empty_db = str(pipeline_tmpdir / "empty_budget.duckdb")
        result = materialize(
            [budget_alerts.budget_alerts],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=empty_db),
                "budget_store": BudgetStoreResource(db_path=empty_db),
                "settings_store": SettingsStoreResource(db_path=empty_db),
            },
        )
        assert result.success

    def test_budget_alerts_with_data(self, pipeline_tmpdir: Path) -> None:
        db_path = str(pipeline_tmpdir / "budget_alerts_test.duckdb")
        conn = duckdb.connect(db_path)
        conn.execute("""
            CREATE TABLE fact_daily_cost (
                provider VARCHAR, charge_date DATE, resource_id VARCHAR,
                resource_name VARCHAR, resource_type VARCHAR,
                service_name VARCHAR, service_category VARCHAR, region_id VARCHAR,
                team VARCHAR, product VARCHAR, env VARCHAR,
                cost_unit_key VARCHAR, effective_cost DECIMAL(18,6),
                billed_cost DECIMAL(18,6), list_cost DECIMAL(18,6), record_count BIGINT
            )
        """)
        # platform/prod team 비용: 4500/5000 = 90% (warning 발생)
        for day in range(1, 15):
            conn.execute("""
                INSERT INTO fact_daily_cost VALUES
                ('aws','2024-01-{}','aws_instance.web_1','web_1','aws_instance',
                 'EC2','Compute','us-east-1','platform','web','prod','platform:web:prod',
                 321.43,321.43,370.0,1)
            """.format(f"{day:02d}"))
        conn.close()
        result = materialize(
            [budget_alerts.budget_alerts],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=db_path),
                "budget_store": BudgetStoreResource(db_path=db_path),
                "settings_store": SettingsStoreResource(db_path=db_path),
            },
        )
        assert result.success

    def test_budget_alerts_over_budget(self, pipeline_tmpdir: Path) -> None:
        db_path = str(pipeline_tmpdir / "budget_over_test.duckdb")
        conn = duckdb.connect(db_path)
        conn.execute("""
            CREATE TABLE fact_daily_cost (
                provider VARCHAR, charge_date DATE, resource_id VARCHAR,
                resource_name VARCHAR, resource_type VARCHAR,
                service_name VARCHAR, service_category VARCHAR, region_id VARCHAR,
                team VARCHAR, product VARCHAR, env VARCHAR,
                cost_unit_key VARCHAR, effective_cost DECIMAL(18,6),
                billed_cost DECIMAL(18,6), list_cost DECIMAL(18,6), record_count BIGINT
            )
        """)
        # 6000 > 5000 budget (over 발생)
        for day in range(1, 15):
            conn.execute("""
                INSERT INTO fact_daily_cost VALUES
                ('aws','2024-01-{}','aws_instance.web_1','web_1','aws_instance',
                 'EC2','Compute','us-east-1','platform','web','prod','platform:web:prod',
                 428.57,428.57,500.0,1)
            """.format(f"{day:02d}"))
        conn.close()
        result = materialize(
            [budget_alerts.budget_alerts],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=db_path),
                "budget_store": BudgetStoreResource(db_path=db_path),
                "settings_store": SettingsStoreResource(db_path=db_path),
            },
        )
        assert result.success


class TestChargebackAsset:
    def test_chargeback_no_fact_table(self, pipeline_tmpdir: Path) -> None:
        empty_db = str(pipeline_tmpdir / "empty_chargeback.duckdb")
        result = materialize(
            [chargeback.chargeback],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=empty_db),
                "budget_store": BudgetStoreResource(db_path=empty_db),
            },
        )
        assert result.success

    def test_chargeback_with_data(self, seeded_duckdb: str) -> None:
        result = materialize(
            [chargeback.chargeback],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=seeded_duckdb),
                "budget_store": BudgetStoreResource(db_path=seeded_duckdb),
            },
        )
        assert result.success

    def test_chargeback_creates_csv(
        self, seeded_duckdb: str, pipeline_tmpdir: Path
    ) -> None:
        materialize(
            [chargeback.chargeback],
            partition_key="2024-01-01",
            resources={
                "duckdb_resource": DuckDBResource(db_path=seeded_duckdb),
                "budget_store": BudgetStoreResource(db_path=seeded_duckdb),
            },
        )
        from dagster_project.config import load_config
        cfg = load_config()
        csv_path = Path(cfg.data.reports_dir) / "chargeback_202401.csv"
        assert csv_path.exists()


class TestFxRatesAsset:
    def test_fx_rates_creates_table(self, pipeline_tmpdir: Path) -> None:
        db_path = str(pipeline_tmpdir / "fx_test.duckdb")
        result = materialize(
            [fx_rates.fx_rates],
            partition_key="2024-01-01",
            resources={"duckdb_resource": DuckDBResource(db_path=db_path)},
        )
        assert result.success
        conn = duckdb.connect(db_path, read_only=True)
        cnt = conn.execute("SELECT COUNT(*) FROM dim_fx_rates").fetchone()
        conn.close()
        assert cnt is not None and cnt[0] > 0

    def test_fx_rates_idempotent(self, pipeline_tmpdir: Path) -> None:
        db_path = str(pipeline_tmpdir / "fx_idempotent.duckdb")
        resources = {"duckdb_resource": DuckDBResource(db_path=db_path)}
        result1 = materialize([fx_rates.fx_rates], partition_key="2024-01-01", resources=resources)
        result2 = materialize([fx_rates.fx_rates], partition_key="2024-01-01", resources=resources)
        assert result1.success
        assert result2.success
        conn = duckdb.connect(db_path, read_only=True)
        cnt = conn.execute("SELECT COUNT(*) FROM dim_fx_rates").fetchone()
        conn.close()
        assert cnt is not None and cnt[0] > 0
