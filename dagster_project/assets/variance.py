"""Variance Asset — Infracost 예측 vs 실제 비용 편차 계산."""


from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..resources.duckdb_io import DuckDBResource
from .raw_cur import MONTHLY_PARTITIONS

_REPORTS_DIR = Path("data/reports")
_VARIANCE_SQL = Path(__file__).parent.parent.parent / "sql" / "marts" / "v_variance.sql"


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
) -> None:
    """예측 vs 실제 비용 편차 리포트 생성.

    status:
      over      → variance_pct > +20%
      under     → variance_pct < -20%
      ok        → -20% <= variance_pct <= +20%
      unmatched → forecast에는 있으나 실제 비용 없음
    """
    partition_key = context.partition_key  # "2024-01-01"
    year_month = partition_key[:7].replace("-", "")  # "202401"
    output_path = _REPORTS_DIR / f"variance_{year_month}.csv"
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with duckdb_resource.get_connection() as conn:
        # dim_forecast 존재 여부 확인
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'dim_forecast'"
        ).fetchall()
        if not tables:
            context.log.warning("dim_forecast not found — skipping variance calculation")
            return

        # v_variance view 생성
        variance_sql = _VARIANCE_SQL.read_text()
        conn.execute(variance_sql)

        # 해당 월 필터 적용하여 CSV 출력
        billing_month = partition_key[:7] + "-01"
        arrow = conn.execute(f"""
            SELECT
                resource_id,
                CAST(forecast_monthly AS DOUBLE) AS forecast_monthly,
                CAST(actual_mtd       AS DOUBLE) AS actual_mtd,
                CAST(variance_abs     AS DOUBLE) AS variance_abs,
                ROUND(CAST(variance_pct AS DOUBLE), 2) AS variance_pct,
                status,
                currency,
                forecast_generated_at
            FROM v_variance
            WHERE billing_month = '{billing_month}' OR billing_month IS NULL
            ORDER BY ABS(COALESCE(variance_pct, 0)) DESC
        """).arrow()

        result = pl.from_arrow(arrow)
        result.write_csv(str(output_path))
        context.log.info(f"Wrote {len(result)} rows to {output_path}")

        over = result.filter(pl.col("status") == "over").height
        under = result.filter(pl.col("status") == "under").height
        unmatched = result.filter(pl.col("status") == "unmatched").height
        context.log.info(f"Status breakdown — over: {over}, under: {under}, unmatched: {unmatched}")
