"""Gold Mart GCP Asset — GCP Silver → fact_daily_cost(provider='gcp') 적재."""


from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..resources.duckdb_io import DuckDBResource
from ..resources.iceberg_catalog import IcebergCatalogResource
from ..resources.settings_store import SettingsStoreResource
from .gold_marts import _INSERT_FACT_SQL, _SQL_DIR
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["silver_focus_gcp"],
    description=(
        "GCP Silver Iceberg 테이블을 DuckDB로 읽어 "
        "fact_daily_cost(provider='gcp')에 적재하고 dim_cost_unit을 재생성한다."
    ),
    group_name="gold",
)
def gold_marts_gcp(
    context: AssetExecutionContext,
    iceberg_catalog: IcebergCatalogResource,
    duckdb_resource: DuckDBResource,
    settings_store: SettingsStoreResource,
) -> None:
    """GCP Silver → Gold 집계 마트 (fact_daily_cost provider='gcp').

    fact_daily_cost는 AWS / GCP 공유 테이블이므로 gold_marts와 독립적으로 실행 가능하다.
    파티션 키별 DELETE + INSERT로 멱등성을 보장한다.
    """
    silver_table = iceberg_catalog.load_table(_cfg.gcp_iceberg.silver_table)
    df: pl.DataFrame = silver_table.scan().to_polars()

    partition_key = context.partition_key
    month_str = partition_key[:7]
    df = df.filter(
        pl.col("ChargePeriodStart").dt.to_string("%Y-%m").str.starts_with(month_str)
    )
    context.log.info(f"[GCP] Silver rows for {month_str}: {len(df)}")

    settings_store.ensure_table()

    with duckdb_resource.get_connection() as conn:
        conn.register("silver_focus_gcp", df.to_arrow())

        fact_ddl = (_SQL_DIR / "fact_daily_cost.sql").read_text()
        conn.execute(fact_ddl)
        conn.execute(
            "ALTER TABLE fact_daily_cost ADD COLUMN IF NOT EXISTS provider VARCHAR DEFAULT 'aws'"
        )

        conn.execute(
            "DELETE FROM fact_daily_cost WHERE provider = 'gcp' AND STRFTIME(charge_date, '%Y-%m') = ?",
            [month_str],
        )
        conn.execute(_INSERT_FACT_SQL.format(provider="gcp", silver_view="silver_focus_gcp"))
        row_count = conn.execute(
            "SELECT COUNT(*) FROM fact_daily_cost WHERE provider = 'gcp' AND STRFTIME(charge_date, '%Y-%m') = ?",
            [month_str],
        ).fetchone()
        context.log.info(f"[GCP] fact_daily_cost (gcp/{month_str}): {row_count[0] if row_count else 0}행")

        # dim_cost_unit 재생성 (전체 데이터 기반)
        dim_sql = (_SQL_DIR / "dim_cost_unit.sql").read_text()
        conn.execute(dim_sql)
        context.log.info("[GCP] Rebuilt dim_cost_unit")
