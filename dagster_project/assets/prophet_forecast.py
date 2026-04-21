"""Prophet Forecast Asset — 시계열 기반 비용 예측 (신뢰구간 포함)."""

from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..db_schema import ensure_tables
from ..providers.prophet_provider import ProphetProvider
from ..resources.duckdb_io import DuckDBResource
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["gold_marts"],
    description=(
        "fact_daily_cost의 historical 데이터로 resource_id별 Prophet 시계열 모델을 학습하고 "
        "다음 달 비용을 예측한다. 신뢰구간 포함하여 dim_prophet_forecast에 저장한다."
    ),
    group_name="forecasting",
)
def prophet_forecast(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
) -> None:
    """Prophet 기반 시계열 비용 예측 실행."""
    partition_key = context.partition_key
    month_str = partition_key[:7]

    with duckdb_resource.get_connection() as conn:
        ensure_tables(conn, "fact_daily_cost", "dim_prophet_forecast")
        cur = conn.cursor()
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='fact_daily_cost'"
        )
        if not cur.fetchone():
            context.log.warning("fact_daily_cost not found — skipping prophet forecast")
            cur.close()
            return

        cur.execute("""
            SELECT charge_date, resource_id,
                   CAST(effective_cost AS DOUBLE PRECISION) AS effective_cost
            FROM fact_daily_cost
            ORDER BY resource_id, charge_date
        """)
        columns = [desc[0] for desc in cur.description]
        raw_rows = cur.fetchall()
        cur.close()

    if not raw_rows:
        context.log.warning("No training data — skipping prophet forecast")
        return

    df = pl.DataFrame(raw_rows, schema=columns, orient="row")
    context.log.info(f"Loaded {len(df)} rows for Prophet training (all partitions)")

    try:
        provider = ProphetProvider(
            forecast_horizon_days=_cfg.prophet.forecast_horizon_days,
            seasonality_mode=_cfg.prophet.seasonality_mode,
        )
        records = provider.forecast_from_df(df)
    except ImportError:
        context.log.warning("prophet 패키지 미설치 — prophet_forecast 건너뜀")
        return

    context.log.info(f"Prophet generated {len(records)} forecast records for partition {month_str}")

    rows = [
        (
            r.resource_address,
            float(r.monthly_cost),
            float(r.lower_bound_monthly_cost),
            float(r.upper_bound_monthly_cost),
            float(r.hourly_cost),
            r.currency,
            r.forecast_generated_at.isoformat(),
        )
        for r in records
    ]

    with duckdb_resource.get_connection() as conn:
        cur = conn.cursor()
        if rows:
            import psycopg2.extras

            resource_ids = [r[0] for r in rows]
            cur.execute(
                "DELETE FROM dim_prophet_forecast WHERE resource_id = ANY(%s)",
                [resource_ids],
            )
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO dim_prophet_forecast
                    (resource_id, predicted_monthly_cost, lower_bound_monthly_cost,
                     upper_bound_monthly_cost, hourly_cost, currency, model_trained_at)
                VALUES %s
                """,
                rows,
                page_size=500,
            )
            context.log.info(f"Inserted {len(rows)} rows into dim_prophet_forecast")
        cur.close()

    reports_dir = Path(_cfg.data.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    year_month = month_str.replace("-", "")
    output_path = reports_dir / f"prophet_forecast_{year_month}.csv"

    if rows:
        pl.DataFrame(
            [
                {
                    "resource_id": r[0], "predicted_monthly_cost": r[1],
                    "lower_bound_monthly_cost": r[2], "upper_bound_monthly_cost": r[3],
                    "hourly_cost": r[4], "currency": r[5], "model_trained_at": r[6],
                }
                for r in rows
            ]
        ).write_csv(str(output_path))
        context.log.info(f"Wrote prophet forecast to {output_path}")
