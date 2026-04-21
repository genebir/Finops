"""Forecast Variance Prophet Asset — Prophet 예측 정확도 분석."""

from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..resources.duckdb_io import DuckDBResource
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()
_REPORTS_DIR = Path(_cfg.data.reports_dir)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dim_forecast_variance_prophet (
    resource_id              VARCHAR        NOT NULL,
    billing_month            VARCHAR        NOT NULL,
    predicted_monthly_cost   DECIMAL(18, 6) NOT NULL,
    lower_bound_monthly_cost DECIMAL(18, 6) NOT NULL DEFAULT 0,
    upper_bound_monthly_cost DECIMAL(18, 6) NOT NULL DEFAULT 0,
    actual_monthly_cost      DECIMAL(18, 6) NOT NULL,
    variance_abs             DECIMAL(18, 6),
    variance_pct             DOUBLE,
    status                   VARCHAR        NOT NULL
)
"""


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["prophet_forecast", "gold_marts"],
    description=(
        "Prophet 예측값(dim_prophet_forecast)과 실제 비용(fact_daily_cost)을 "
        "resource_id 기준으로 조인하여 예측 정확도를 계산한다. "
        "신뢰구간 내 실제값 비율을 포함하며 data/reports/prophet_variance_YYYYMM.csv에 저장한다."
    ),
    group_name="forecasting",
)
def forecast_variance_prophet(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
) -> None:
    """Prophet 예측 vs 실제 비용 편차 분석.

    status:
      within_bounds  — 실제값이 신뢰구간(lower~upper) 내
      above_upper    — 실제값이 upper_bound 초과
      below_lower    — 실제값이 lower_bound 미만
      no_actual      — 해당 월 실제 데이터 없음
    """
    partition_key = context.partition_key
    month_str = partition_key[:7]
    year_month = month_str.replace("-", "")
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with duckdb_resource.get_connection() as conn:
        prophet_exists = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name = 'dim_prophet_forecast'"
        ).fetchall()
        if not prophet_exists:
            context.log.warning("dim_prophet_forecast not found — skipping forecast_variance_prophet")
            return

        fact_exists = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'fact_daily_cost'"
        ).fetchall()
        if not fact_exists:
            context.log.warning("fact_daily_cost not found — skipping forecast_variance_prophet")
            return

        arrow = conn.execute(f"""
            WITH actual AS (
                SELECT
                    resource_id,
                    SUM(CAST(effective_cost AS DOUBLE)) AS actual_monthly_cost
                FROM fact_daily_cost
                WHERE STRFTIME(charge_date, '%Y-%m') = '{month_str}'
                GROUP BY resource_id
            )
            SELECT
                p.resource_id,
                '{month_str}'                                                    AS billing_month,
                CAST(p.predicted_monthly_cost   AS DOUBLE)                       AS predicted_monthly_cost,
                CAST(p.lower_bound_monthly_cost AS DOUBLE)                       AS lower_bound_monthly_cost,
                CAST(p.upper_bound_monthly_cost AS DOUBLE)                       AS upper_bound_monthly_cost,
                COALESCE(a.actual_monthly_cost, 0.0)                             AS actual_monthly_cost,
                COALESCE(a.actual_monthly_cost, 0.0)
                    - CAST(p.predicted_monthly_cost AS DOUBLE)                   AS variance_abs,
                CASE
                    WHEN CAST(p.predicted_monthly_cost AS DOUBLE) = 0 THEN NULL
                    ELSE (COALESCE(a.actual_monthly_cost, 0.0)
                          - CAST(p.predicted_monthly_cost AS DOUBLE))
                         / CAST(p.predicted_monthly_cost AS DOUBLE) * 100
                END                                                              AS variance_pct,
                CASE
                    WHEN a.resource_id IS NULL
                        THEN 'no_actual'
                    WHEN COALESCE(a.actual_monthly_cost, 0.0)
                         > CAST(p.upper_bound_monthly_cost AS DOUBLE)
                        THEN 'above_upper'
                    WHEN COALESCE(a.actual_monthly_cost, 0.0)
                         < CAST(p.lower_bound_monthly_cost AS DOUBLE)
                        THEN 'below_lower'
                    ELSE 'within_bounds'
                END                                                              AS status
            FROM dim_prophet_forecast p
            LEFT JOIN actual a ON p.resource_id = a.resource_id
        """).arrow()

    df = pl.from_arrow(arrow)
    assert isinstance(df, pl.DataFrame)

    within = (df["status"] == "within_bounds").sum()
    total = len(df)
    context.log.info(
        f"Prophet variance for {month_str}: {total} resources, "
        f"{within}/{total} within bounds ({within / total * 100:.1f}% accuracy)"
        if total > 0 else f"Prophet variance for {month_str}: no data"
    )

    with duckdb_resource.get_connection() as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute(
            "DELETE FROM dim_forecast_variance_prophet WHERE billing_month = ?",
            [month_str],
        )
        if not df.is_empty():
            conn.register("variance_rows", df.to_arrow())
            conn.execute("""
                INSERT INTO dim_forecast_variance_prophet
                SELECT
                    resource_id,
                    billing_month,
                    CAST(predicted_monthly_cost   AS DECIMAL(18,6)),
                    CAST(lower_bound_monthly_cost AS DECIMAL(18,6)),
                    CAST(upper_bound_monthly_cost AS DECIMAL(18,6)),
                    CAST(actual_monthly_cost      AS DECIMAL(18,6)),
                    CAST(variance_abs             AS DECIMAL(18,6)),
                    variance_pct,
                    status
                FROM variance_rows
            """)

    output_path = _REPORTS_DIR / f"prophet_variance_{year_month}.csv"
    df.write_csv(str(output_path))
    context.log.info(f"Wrote prophet variance report to {output_path}")
