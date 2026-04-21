"""Prophet Forecast Asset — 시계열 기반 비용 예측 (신뢰구간 포함)."""

from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..providers.prophet_provider import ProphetProvider
from ..resources.duckdb_io import DuckDBResource
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dim_prophet_forecast (
    resource_id              VARCHAR        NOT NULL,
    predicted_monthly_cost   DECIMAL(18, 6) NOT NULL,
    lower_bound_monthly_cost DECIMAL(18, 6) NOT NULL DEFAULT 0,
    upper_bound_monthly_cost DECIMAL(18, 6) NOT NULL DEFAULT 0,
    hourly_cost              DECIMAL(18, 6) NOT NULL,
    currency                 VARCHAR        NOT NULL,
    model_trained_at         TIMESTAMPTZ    NOT NULL
)
"""


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["gold_marts"],
    description=(
        "fact_daily_cost의 historical 데이터로 resource_id별 Prophet 시계열 모델을 학습하고 "
        "다음 달 비용을 예측한다. 예측값(yhat)과 신뢰구간(lower/upper)을 "
        "dim_prophet_forecast 테이블(DuckDB)에 저장한다. "
        "학습 데이터 14일 미만 리소스는 제외된다."
    ),
    group_name="forecasting",
)
def prophet_forecast(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
) -> None:
    """Prophet 기반 시계열 비용 예측 실행 (신뢰구간 포함).

    infracost 기반 dim_forecast와는 별도의 dim_prophet_forecast 테이블에 적재한다.
    resource_id 기준 DELETE + INSERT로 멱등성을 보장한다.
    """
    partition_key = context.partition_key
    month_str = partition_key[:7]

    with duckdb_resource.get_connection() as conn:
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'fact_daily_cost'"
        ).fetchall()
        if not tables:
            context.log.warning("fact_daily_cost not found — skipping prophet forecast")
            return

        arrow = conn.execute("""
            SELECT
                charge_date,
                resource_id,
                CAST(effective_cost AS DOUBLE) AS effective_cost
            FROM fact_daily_cost
            ORDER BY resource_id, charge_date
        """).arrow()

    _raw = pl.from_arrow(arrow)
    assert isinstance(_raw, pl.DataFrame)
    df: pl.DataFrame = _raw
    context.log.info(f"Loaded {len(df)} rows for Prophet training (all partitions)")

    if df.is_empty():
        context.log.warning("No training data — skipping prophet forecast")
        return

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
        {
            "resource_id": r.resource_address,
            "predicted_monthly_cost": float(r.monthly_cost),
            "lower_bound_monthly_cost": float(r.lower_bound_monthly_cost),
            "upper_bound_monthly_cost": float(r.upper_bound_monthly_cost),
            "hourly_cost": float(r.hourly_cost),
            "currency": r.currency,
            "model_trained_at": r.forecast_generated_at.isoformat(),
        }
        for r in records
    ]

    with duckdb_resource.get_connection() as conn:
        conn.execute(_CREATE_TABLE_SQL)
        # Phase 3 마이그레이션: 신뢰구간 컬럼 추가
        conn.execute(
            "ALTER TABLE dim_prophet_forecast ADD COLUMN IF NOT EXISTS "
            "lower_bound_monthly_cost DECIMAL(18,6) DEFAULT 0"
        )
        conn.execute(
            "ALTER TABLE dim_prophet_forecast ADD COLUMN IF NOT EXISTS "
            "upper_bound_monthly_cost DECIMAL(18,6) DEFAULT 0"
        )

        if rows:
            forecast_df = pl.DataFrame(rows)
            conn.register("prophet_rows", forecast_df.to_arrow())
            conn.execute("""
                DELETE FROM dim_prophet_forecast
                WHERE resource_id IN (SELECT resource_id FROM prophet_rows)
            """)
            conn.execute("""
                INSERT INTO dim_prophet_forecast
                SELECT
                    resource_id,
                    CAST(predicted_monthly_cost    AS DECIMAL(18,6)),
                    CAST(lower_bound_monthly_cost  AS DECIMAL(18,6)),
                    CAST(upper_bound_monthly_cost  AS DECIMAL(18,6)),
                    CAST(hourly_cost               AS DECIMAL(18,6)),
                    currency,
                    CAST(model_trained_at AS TIMESTAMPTZ)
                FROM prophet_rows
            """)
            context.log.info(f"Inserted {len(rows)} rows into dim_prophet_forecast")

    reports_dir = Path(_cfg.data.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    year_month = month_str.replace("-", "")
    output_path = reports_dir / f"prophet_forecast_{year_month}.csv"

    if rows:
        pl.DataFrame(rows).write_csv(str(output_path))
        context.log.info(f"Wrote prophet forecast to {output_path}")
