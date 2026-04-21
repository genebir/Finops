"""Silver Azure Asset — Bronze Iceberg Azure → Polars 정제, Tags 평탄화, CostUnit 파생."""


import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..resources.iceberg_catalog import IcebergCatalogResource
from ..utils.silver_transforms import flatten_tags
from .raw_cur import MONTHLY_PARTITIONS
from .silver_focus import _SILVER_ICEBERG_SCHEMA, _SILVER_PARTITION_SPEC

_cfg = load_config()


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["bronze_iceberg_azure"],
    description=(
        "Azure Bronze Iceberg 테이블을 Polars로 읽어 Tags를 team/product/env 컬럼으로 "
        "평탄화하고 cost_unit_key를 파생한 뒤 Silver 테이블에 overwrite 적재한다."
    ),
    group_name="silver",
)
def silver_focus_azure(
    context: AssetExecutionContext,
    iceberg_catalog: IcebergCatalogResource,
) -> None:
    """Azure Bronze → Silver 변환.

    - Tags JSON → team, product, env 분리
    - cost_unit_key = team:product:env
    - 멱등성: overwrite
    """
    bronze_table_name = _cfg.azure_iceberg.bronze_table
    silver_table_name = _cfg.azure_iceberg.silver_table

    bronze_table = iceberg_catalog.load_table(bronze_table_name)
    df: pl.DataFrame = bronze_table.scan().to_polars()

    context.log.info(f"[Azure] Read {len(df)} rows from {bronze_table_name}")

    partition_key = context.partition_key
    month_str = partition_key[:7]
    df = df.filter(
        pl.col("ChargePeriodStart").dt.to_string("%Y-%m").str.starts_with(month_str)
    )
    context.log.info(f"[Azure] Filtered to {len(df)} rows for {month_str}")

    df = flatten_tags(df)

    silver_iceberg_table = iceberg_catalog.ensure_table(
        silver_table_name,
        schema=_SILVER_ICEBERG_SCHEMA,
        partition_spec=_SILVER_PARTITION_SPEC,
    )
    silver_iceberg_table.overwrite(df.to_arrow())
    context.log.info(f"[Azure] Wrote {len(df)} rows to {silver_table_name}")
