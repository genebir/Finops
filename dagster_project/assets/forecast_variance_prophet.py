"""Forecast Variance Prophet Asset — Prophet 예측 정확도 분석."""

from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..db_schema import ensure_tables
from ..resources.duckdb_io import DuckDBResource
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()
_REPORTS_DIR = Path(_cfg.data.reports_dir)


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["prophet_forecast", "gold_marts"],
    description=(
        "Prophet 예측값(dim_prophet_forecast)과 실제 비용(fact_daily_cost)을 "
        "resource_id 기준으로 조인하여 예측 정확도를 계산한다."
    ),
    group_name="forecasting",
)
def forecast_variance_prophet(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
) -> None:
    """Prophet 예측 vs 실제 비용 편차 분석."""
    partition_key = context.partition_key
    month_str = partition_key[:7]
    year_month = month_str.replace("-", "")
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with duckdb_resource.get_connection() as conn:
        ensure_tables(
            conn, "fact_daily_cost", "dim_prophet_forecast", "dim_forecast_variance_prophet"
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='dim_prophet_forecast'"
        )
        if not cur.fetchone():
            context.log.warning("dim_prophet_forecast not found — skipping")
            cur.close()
            return

        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='fact_daily_cost'"
        )
        if not cur.fetchone():
            context.log.warning("fact_daily_cost not found — skipping")
            cur.close()
            return

        cur.execute("""
            WITH actual AS (
                SELECT resource_id,
                       SUM(CAST(effective_cost AS DOUBLE PRECISION)) AS actual_monthly_cost
                FROM fact_daily_cost
                WHERE to_char(charge_date, 'YYYY-MM') = %s
                GROUP BY resource_id
            )
            SELECT
                p.resource_id,
                %s AS billing_month,
                CAST(p.predicted_monthly_cost AS DOUBLE PRECISION),
                CAST(p.lower_bound_monthly_cost AS DOUBLE PRECISION),
                CAST(p.upper_bound_monthly_cost AS DOUBLE PRECISION),
                COALESCE(a.actual_monthly_cost, 0.0) AS actual_monthly_cost,
                COALESCE(a.actual_monthly_cost, 0.0)
                    - CAST(p.predicted_monthly_cost AS DOUBLE PRECISION) AS variance_abs,
                CASE
                    WHEN CAST(p.predicted_monthly_cost AS DOUBLE PRECISION) = 0 THEN NULL
                    ELSE (COALESCE(a.actual_monthly_cost, 0.0)
                          - CAST(p.predicted_monthly_cost AS DOUBLE PRECISION))
                         / CAST(p.predicted_monthly_cost AS DOUBLE PRECISION) * 100
                END AS variance_pct,
                CASE
                    WHEN a.resource_id IS NULL THEN 'no_actual'
                    WHEN COALESCE(a.actual_monthly_cost, 0.0)
                         > CAST(p.upper_bound_monthly_cost AS DOUBLE PRECISION)
                        THEN 'above_upper'
                    WHEN COALESCE(a.actual_monthly_cost, 0.0)
                         < CAST(p.lower_bound_monthly_cost AS DOUBLE PRECISION)
                        THEN 'below_lower'
                    ELSE 'within_bounds'
                END AS status
            FROM dim_prophet_forecast p
            LEFT JOIN actual a ON p.resource_id = a.resource_id
        """, [month_str, month_str])

        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()

    df = pl.DataFrame(rows, schema=columns, orient="row") if rows else pl.DataFrame()

    if not df.is_empty():
        within = (df["status"] == "within_bounds").sum()
        total = len(df)
        context.log.info(
            f"Prophet variance for {month_str}: {total} resources, "
            f"{within}/{total} within bounds ({within / total * 100:.1f}% accuracy)"
        )

    with duckdb_resource.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM dim_forecast_variance_prophet WHERE billing_month = %s",
            [month_str],
        )
        if not df.is_empty():
            import psycopg2.extras

            values = [
                (
                    row["resource_id"], row["billing_month"],
                    row["predicted_monthly_cost"], row["lower_bound_monthly_cost"],
                    row["upper_bound_monthly_cost"], row["actual_monthly_cost"],
                    row["variance_abs"], row["variance_pct"], row["status"],
                )
                for row in df.iter_rows(named=True)
            ]
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO dim_forecast_variance_prophet
                    (resource_id, billing_month, predicted_monthly_cost,
                     lower_bound_monthly_cost, upper_bound_monthly_cost,
                     actual_monthly_cost, variance_abs, variance_pct, status)
                VALUES %s
                """,
                values,
                page_size=500,
            )
        cur.close()

    output_path = _REPORTS_DIR / f"prophet_variance_{year_month}.csv"
    if not df.is_empty():
        df.write_csv(str(output_path))
    context.log.info(f"Wrote prophet variance report to {output_path}")
