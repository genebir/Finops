"""Gold Mart GCP Asset — GCP Silver → fact_daily_cost(provider='gcp') 적재."""


import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..resources.duckdb_io import DuckDBResource
from ..resources.iceberg_catalog import IcebergCatalogResource
from ..resources.settings_store import SettingsStoreResource
from .gold_marts import _insert_fact_from_silver, _rebuild_dim_cost_unit
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["silver_focus_gcp"],
    description=(
        "GCP Silver Iceberg 테이블을 PostgreSQL로 읽어 "
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
    """GCP Silver → Gold 집계 마트 (fact_daily_cost provider='gcp')."""
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
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM fact_daily_cost WHERE provider = 'gcp' AND to_char(charge_date, 'YYYY-MM') = %s",
            [month_str],
        )
        row_count = _insert_fact_from_silver(conn, df, "gcp")
        context.log.info(f"[GCP] fact_daily_cost (gcp/{month_str}): {row_count}행")

        _rebuild_dim_cost_unit(conn)
        context.log.info("[GCP] Rebuilt dim_cost_unit")
        cur.close()
