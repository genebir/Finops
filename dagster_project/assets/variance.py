"""Variance Asset — Infracost 예측 vs 실제 비용 편차 계산."""


from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..resources.duckdb_io import DuckDBResource
from ..resources.settings_store import SettingsStoreResource
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()
_REPORTS_DIR = Path(_cfg.data.reports_dir)


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["gold_marts", "infracost_forecast"],
    description=(
        "Infracost 예측(dim_forecast)과 실제 비용(fact_daily_cost)을 ResourceId 기준으로 "
        "LEFT JOIN하여 편차를 계산하고 data/reports/variance_YYYYMM.csv를 출력한다."
    ),
    group_name="reporting",
)
def variance(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
    settings_store: SettingsStoreResource,
) -> None:
    """예측 vs 실제 비용 편차 리포트 생성."""
    partition_key = context.partition_key
    year_month = partition_key[:7].replace("-", "")
    month_str = partition_key[:7]
    output_path = _REPORTS_DIR / f"variance_{year_month}.csv"
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with duckdb_resource.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='dim_forecast'"
        )
        if not cur.fetchone():
            context.log.warning("dim_forecast not found — skipping variance calculation")
            cur.close()
            return

        settings_store.ensure_table()
        over_pct = settings_store.get_float(
            "variance.threshold.over_pct", _cfg.operational_defaults.variance_over_pct
        )
        under_pct = settings_store.get_float(
            "variance.threshold.under_pct", abs(_cfg.operational_defaults.variance_under_pct)
        )

        cur.execute("DROP VIEW IF EXISTS v_variance")
        cur.execute(f"""
            CREATE VIEW v_variance AS
            WITH actual_mtd AS (
                SELECT resource_id,
                       DATE_TRUNC('month', charge_date)::DATE AS billing_month,
                       SUM(effective_cost) AS actual_mtd
                FROM fact_daily_cost
                GROUP BY resource_id, DATE_TRUNC('month', charge_date)
            )
            SELECT
                f.resource_address AS resource_id,
                f.monthly_cost AS forecast_monthly,
                COALESCE(a.actual_mtd, 0) AS actual_mtd,
                COALESCE(a.actual_mtd, 0) - f.monthly_cost AS variance_abs,
                CASE WHEN f.monthly_cost = 0 THEN NULL
                     ELSE (COALESCE(a.actual_mtd, 0) - f.monthly_cost)
                          / f.monthly_cost * 100
                END AS variance_pct,
                CASE
                    WHEN a.resource_id IS NULL THEN 'unmatched'
                    WHEN (COALESCE(a.actual_mtd, 0) - f.monthly_cost)
                         / NULLIF(f.monthly_cost, 0) * 100 > {over_pct} THEN 'over'
                    WHEN (COALESCE(a.actual_mtd, 0) - f.monthly_cost)
                         / NULLIF(f.monthly_cost, 0) * 100 < -{under_pct} THEN 'under'
                    ELSE 'ok'
                END AS status,
                f.currency,
                f.forecast_generated_at,
                a.billing_month::VARCHAR
            FROM dim_forecast f
            LEFT JOIN actual_mtd a ON f.resource_address = a.resource_id
        """)

        billing_month = partition_key[:7] + "-01"
        cur.execute("""
            SELECT resource_id,
                   CAST(forecast_monthly AS DOUBLE PRECISION),
                   CAST(actual_mtd AS DOUBLE PRECISION),
                   CAST(variance_abs AS DOUBLE PRECISION),
                   ROUND(CAST(variance_pct AS NUMERIC), 2),
                   status, currency, forecast_generated_at
            FROM v_variance
            WHERE billing_month = %s OR billing_month IS NULL
            ORDER BY ABS(COALESCE(variance_pct, 0)) DESC
        """, [billing_month])

        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()

    result = pl.DataFrame(rows, schema=columns, orient="row") if rows else pl.DataFrame(
        schema={c: pl.Utf8 for c in ["resource_id", "forecast_monthly", "actual_mtd",
                                      "variance_abs", "variance_pct", "status",
                                      "currency", "forecast_generated_at"]}
    )
    result.write_csv(str(output_path))
    context.log.info(f"Wrote {len(result)} rows to {output_path}")

    if not result.is_empty():
        over = result.filter(pl.col("status") == "over").height
        under = result.filter(pl.col("status") == "under").height
        unmatched = result.filter(pl.col("status") == "unmatched").height
        context.log.info(f"Status breakdown — over: {over}, under: {under}, unmatched: {unmatched}")
