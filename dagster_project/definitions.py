"""Dagster Definitions 엔트리포인트 — 모든 asset과 resource 등록."""

from __future__ import annotations

from dagster import Definitions, load_assets_from_modules

from .assets import (
    alert_dispatch,
    anomaly_detection,
    bronze_iceberg,
    bronze_iceberg_azure,
    bronze_iceberg_gcp,
    budget_alerts,
    burn_rate,
    chargeback,
    cost_allocation,
    cost_recommendations,
    showback_report,
    data_quality,
    forecast_variance_prophet,
    fx_rates,
    gold_marts,
    gold_marts_azure,
    gold_marts_gcp,
    infracost_forecast,
    prophet_forecast,
    raw_cur,
    raw_cur_azure,
    raw_cur_gcp,
    resource_inventory,
    tag_policy,
    silver_focus,
    silver_focus_azure,
    silver_focus_gcp,
    variance,
)
from .config import load_config
from .resources.budget_store import BudgetStoreResource
from .resources.duckdb_io import DuckDBResource
from .resources.iceberg_catalog import IcebergCatalogResource
from .resources.infracost_cli import InfracostCliResource
from .resources.settings_store import SettingsStoreResource
from .schedules.monthly import (
    daily_data_quality_schedule,
    monthly_burn_rate_schedule,
)
from .sensors.run_logger import (
    pipeline_run_failure_sensor,
    pipeline_run_success_sensor,
)

_cfg = load_config()

all_assets = load_assets_from_modules(
    [
        raw_cur,
        raw_cur_gcp,
        raw_cur_azure,
        bronze_iceberg,
        bronze_iceberg_gcp,
        bronze_iceberg_azure,
        silver_focus,
        silver_focus_gcp,
        silver_focus_azure,
        gold_marts,
        gold_marts_gcp,
        gold_marts_azure,
        infracost_forecast,
        variance,
        anomaly_detection,
        alert_dispatch,
        prophet_forecast,
        forecast_variance_prophet,
        budget_alerts,
        chargeback,
        fx_rates,
        cost_recommendations,
        data_quality,
        burn_rate,
        resource_inventory,
        tag_policy,
        cost_allocation,
        showback_report,
    ]
)

defs = Definitions(
    assets=all_assets,
    sensors=[pipeline_run_success_sensor, pipeline_run_failure_sensor],
    schedules=[monthly_burn_rate_schedule, daily_data_quality_schedule],
    resources={
        "iceberg_catalog": IcebergCatalogResource(
            warehouse_path=_cfg.data.warehouse_path,
            catalog_db_path=_cfg.data.catalog_db_path,
        ),
        "duckdb_resource": DuckDBResource(),
        "infracost_cli": InfracostCliResource(
            terraform_path=_cfg.infracost.terraform_path,
            infracost_binary=_cfg.infracost.binary,
            subprocess_timeout_sec=_cfg.infracost.subprocess_timeout_sec,
        ),
        "settings_store": SettingsStoreResource(),
        "budget_store": BudgetStoreResource(),
    },
)
