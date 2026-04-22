"""Pipeline trigger endpoints — run Dagster assets from the web UI."""

from __future__ import annotations

import time
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from ..deps import db_write
from ..models.pipeline import (
    AssetInfo,
    AssetListResponse,
    PipelinePreset,
    TriggerRequest,
    TriggerResponse,
    TriggerResult,
)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])
log = logging.getLogger(__name__)

_PRESETS: list[PipelinePreset] = [
    PipelinePreset(
        name="full_ingestion",
        description="Full pipeline: Raw → Bronze → Silver → Gold (all 3 clouds)",
        assets=[
            "raw_cur", "raw_cur_gcp", "raw_cur_azure",
            "bronze_iceberg", "bronze_iceberg_gcp", "bronze_iceberg_azure",
            "silver_focus", "silver_focus_gcp", "silver_focus_azure",
            "gold_marts", "gold_marts_gcp", "gold_marts_azure",
        ],
    ),
    PipelinePreset(
        name="analytics",
        description="Analytics layer: anomaly detection, forecasts, budgets, recommendations",
        assets=[
            "anomaly_detection", "alert_dispatch",
            "prophet_forecast", "forecast_variance_prophet",
            "budget_alerts", "chargeback",
            "cost_recommendations", "burn_rate",
            "cost_trend", "savings_tracker",
            "budget_forecast", "showback_report",
        ],
    ),
    PipelinePreset(
        name="compliance",
        description="Compliance: resource inventory, tag policy, tag compliance, data quality",
        assets=[
            "resource_inventory", "tag_policy",
            "tag_compliance_score", "data_quality",
        ],
    ),
    PipelinePreset(
        name="support",
        description="Support tables: FX rates, cost allocation",
        assets=["fx_rates", "cost_allocation"],
    ),
]


def _get_asset_map() -> dict[str, Any]:
    """Lazily load Dagster definitions and build asset module map."""
    from dagster_project.assets import (
        alert_dispatch,
        anomaly_detection,
        bronze_iceberg,
        bronze_iceberg_azure,
        bronze_iceberg_gcp,
        budget_alerts,
        budget_forecast,
        burn_rate,
        chargeback,
        cost_allocation,
        cost_recommendations,
        cost_trend,
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
        savings_tracker,
        showback_report,
        silver_focus,
        silver_focus_azure,
        silver_focus_gcp,
        tag_compliance_score,
        tag_policy,
        variance,
    )

    return {
        "raw_cur": raw_cur,
        "raw_cur_gcp": raw_cur_gcp,
        "raw_cur_azure": raw_cur_azure,
        "bronze_iceberg": bronze_iceberg,
        "bronze_iceberg_gcp": bronze_iceberg_gcp,
        "bronze_iceberg_azure": bronze_iceberg_azure,
        "silver_focus": silver_focus,
        "silver_focus_gcp": silver_focus_gcp,
        "silver_focus_azure": silver_focus_azure,
        "gold_marts": gold_marts,
        "gold_marts_gcp": gold_marts_gcp,
        "gold_marts_azure": gold_marts_azure,
        "infracost_forecast": infracost_forecast,
        "variance": variance,
        "anomaly_detection": anomaly_detection,
        "alert_dispatch": alert_dispatch,
        "prophet_forecast": prophet_forecast,
        "forecast_variance_prophet": forecast_variance_prophet,
        "budget_alerts": budget_alerts,
        "chargeback": chargeback,
        "fx_rates": fx_rates,
        "cost_recommendations": cost_recommendations,
        "data_quality": data_quality,
        "burn_rate": burn_rate,
        "resource_inventory": resource_inventory,
        "tag_policy": tag_policy,
        "cost_allocation": cost_allocation,
        "showback_report": showback_report,
        "cost_trend": cost_trend,
        "savings_tracker": savings_tracker,
        "budget_forecast": budget_forecast,
        "tag_compliance_score": tag_compliance_score,
    }


_ASSET_GROUPS: dict[str, str] = {
    "raw_cur": "ingestion", "raw_cur_gcp": "ingestion", "raw_cur_azure": "ingestion",
    "bronze_iceberg": "ingestion", "bronze_iceberg_gcp": "ingestion", "bronze_iceberg_azure": "ingestion",
    "silver_focus": "transform", "silver_focus_gcp": "transform", "silver_focus_azure": "transform",
    "gold_marts": "marts", "gold_marts_gcp": "marts", "gold_marts_azure": "marts",
    "anomaly_detection": "analytics", "alert_dispatch": "analytics",
    "prophet_forecast": "forecast", "forecast_variance_prophet": "forecast",
    "infracost_forecast": "forecast", "variance": "forecast",
    "budget_alerts": "budget", "chargeback": "budget", "burn_rate": "budget",
    "budget_forecast": "budget", "savings_tracker": "budget", "showback_report": "budget",
    "cost_recommendations": "analytics", "cost_trend": "analytics", "cost_allocation": "budget",
    "fx_rates": "support", "data_quality": "compliance",
    "resource_inventory": "compliance", "tag_policy": "compliance", "tag_compliance_score": "compliance",
}

_PARTITIONED_ASSETS = {
    "raw_cur", "raw_cur_gcp", "raw_cur_azure",
    "bronze_iceberg", "bronze_iceberg_gcp", "bronze_iceberg_azure",
    "silver_focus", "silver_focus_gcp", "silver_focus_azure",
    "gold_marts", "gold_marts_gcp", "gold_marts_azure",
    "anomaly_detection", "alert_dispatch", "variance",
    "prophet_forecast", "forecast_variance_prophet", "infracost_forecast",
    "budget_alerts", "chargeback", "fx_rates",
    "cost_recommendations",
}

_DESCRIPTIONS: dict[str, str] = {
    "raw_cur": "Generate synthetic AWS CUR data",
    "raw_cur_gcp": "Generate synthetic GCP billing data",
    "raw_cur_azure": "Generate synthetic Azure billing data",
    "bronze_iceberg": "Load AWS data into Iceberg Bronze",
    "bronze_iceberg_gcp": "Load GCP data into Iceberg Bronze",
    "bronze_iceberg_azure": "Load Azure data into Iceberg Bronze",
    "silver_focus": "Transform AWS data to FOCUS v1 Silver",
    "silver_focus_gcp": "Transform GCP data to FOCUS v1 Silver",
    "silver_focus_azure": "Transform Azure data to FOCUS v1 Silver",
    "gold_marts": "Build AWS Gold marts (PostgreSQL)",
    "gold_marts_gcp": "Build GCP Gold marts (PostgreSQL)",
    "gold_marts_azure": "Build Azure Gold marts (PostgreSQL)",
    "anomaly_detection": "Detect cost anomalies (multi-detector)",
    "alert_dispatch": "Dispatch alerts (console/Slack/email)",
    "prophet_forecast": "Prophet time-series forecast",
    "forecast_variance_prophet": "Prophet forecast accuracy",
    "infracost_forecast": "Infracost Terraform forecast",
    "variance": "Infracost vs actual variance",
    "budget_alerts": "Budget utilization alerts",
    "chargeback": "Team chargeback report",
    "burn_rate": "MTD burn rate monitoring",
    "budget_forecast": "Budget EOM forecast",
    "savings_tracker": "Savings realization tracking",
    "showback_report": "Team showback report",
    "cost_recommendations": "Cost optimization recommendations",
    "cost_trend": "Monthly cost trend rollup",
    "cost_allocation": "Cost allocation by rules",
    "fx_rates": "FX exchange rates",
    "data_quality": "Data quality validation",
    "resource_inventory": "Resource inventory + tag completeness",
    "tag_policy": "Tag policy violation check",
    "tag_compliance_score": "Tag compliance score",
}


@router.get("/assets")
def list_assets() -> AssetListResponse:
    """List all available pipeline assets."""
    assets = [
        AssetInfo(
            key=key,
            group=_ASSET_GROUPS.get(key),
            description=_DESCRIPTIONS.get(key),
            has_partitions=key in _PARTITIONED_ASSETS,
        )
        for key in sorted(_ASSET_GROUPS.keys())
    ]
    return AssetListResponse(assets=assets, total=len(assets))


@router.get("/presets")
def list_presets() -> list[PipelinePreset]:
    """List available pipeline run presets."""
    return _PRESETS


@router.post("/trigger")
def trigger_pipeline(req: TriggerRequest) -> TriggerResponse:
    """Trigger materialization of selected assets.

    Runs synchronously using dagster.materialize().
    For partitioned assets, partition_key is required (format: YYYY-MM-DD).
    """
    from dagster import materialize as dag_materialize

    from dagster_project.config import load_config
    from dagster_project.resources.budget_store import BudgetStoreResource
    from dagster_project.resources.duckdb_io import DuckDBResource
    from dagster_project.resources.iceberg_catalog import IcebergCatalogResource
    from dagster_project.resources.infracost_cli import InfracostCliResource
    from dagster_project.resources.settings_store import SettingsStoreResource

    asset_map = _get_asset_map()

    unknown = [a for a in req.assets if a not in asset_map]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown assets: {unknown}")

    needs_partition = any(a in _PARTITIONED_ASSETS for a in req.assets)
    if needs_partition and not req.partition_key:
        raise HTTPException(
            status_code=400,
            detail="partition_key is required for partitioned assets (format: YYYY-MM-DD)",
        )

    cfg = load_config()
    import tempfile
    from pathlib import Path

    tmpdir = tempfile.mkdtemp(prefix="finops_trigger_")
    resources = {
        "iceberg_catalog": IcebergCatalogResource(
            warehouse_path=str(Path(tmpdir) / "warehouse"),
            catalog_db_path=str(Path(tmpdir) / "catalog.db"),
        ),
        "duckdb_resource": DuckDBResource(),
        "settings_store": SettingsStoreResource(),
        "budget_store": BudgetStoreResource(),
        "infracost_cli": InfracostCliResource(
            terraform_path=cfg.infracost.terraform_path,
            infracost_binary=cfg.infracost.binary,
            subprocess_timeout_sec=cfg.infracost.subprocess_timeout_sec,
        ),
    }

    results: list[TriggerResult] = []
    for asset_key in req.assets:
        module = asset_map[asset_key]
        asset_fn = getattr(module, asset_key)
        t0 = time.monotonic()
        try:
            kwargs: dict[str, Any] = {"resources": resources}
            if asset_key in _PARTITIONED_ASSETS and req.partition_key:
                kwargs["partition_key"] = req.partition_key
            result = dag_materialize([asset_fn], **kwargs)
            dur = round(time.monotonic() - t0, 2)
            if result.success:
                results.append(TriggerResult(
                    asset_key=asset_key, success=True, duration_sec=dur,
                ))
            else:
                err_events = [
                    e for e in result.all_events
                    if e.is_step_failure
                ]
                err_msg = str(err_events[0]) if err_events else "Unknown failure"
                results.append(TriggerResult(
                    asset_key=asset_key, success=False,
                    error=err_msg[:500], duration_sec=dur,
                ))
        except Exception as exc:
            dur = round(time.monotonic() - t0, 2)
            results.append(TriggerResult(
                asset_key=asset_key, success=False,
                error=str(exc)[:500], duration_sec=dur,
            ))

    _log_trigger_results(results, req.partition_key)

    succeeded = sum(1 for r in results if r.success)
    return TriggerResponse(
        results=results,
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
    )


def _log_trigger_results(
    results: list[TriggerResult],
    partition_key: str | None,
) -> None:
    """Log trigger results to pipeline_run_log table."""
    try:
        with db_write() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname='public' AND tablename='pipeline_run_log'"
                )
                if not cur.fetchone():
                    return
                now = datetime.now(tz=UTC)
                for r in results:
                    finished = datetime.now(tz=UTC)
                    cur.execute(
                        "INSERT INTO pipeline_run_log "
                        "(run_id, asset_key, partition_key, status, started_at, finished_at, "
                        " duration_sec, row_count, error_message) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        [
                            f"web-trigger-{now.strftime('%Y%m%d%H%M%S')}",
                            r.asset_key,
                            partition_key,
                            "success" if r.success else "failure",
                            now,
                            finished,
                            r.duration_sec,
                            None,
                            r.error,
                        ],
                    )
    except Exception as exc:
        log.warning("Failed to log trigger results: %s", exc)
