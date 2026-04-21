"""Silver Asset — Bronze Iceberg → Polars 정제, Tags 평탄화, CostUnit 파생."""


import json

import polars as pl
from dagster import AssetExecutionContext, asset
from pyiceberg.partitioning import PartitionField, PartitionSpec
from pyiceberg.schema import Schema
from pyiceberg.transforms import MonthTransform
from pyiceberg.types import (
    NestedField,
    StringType,
    TimestamptzType,
)

from ..resources.iceberg_catalog import IcebergCatalogResource
from .raw_cur import MONTHLY_PARTITIONS

_BRONZE_TABLE = "focus.bronze_cur"
_SILVER_TABLE = "focus.silver_focus"

# Polars가 Iceberg scan 결과를 모두 nullable로 반환하므로 required=False로 통일
_SILVER_ICEBERG_SCHEMA = Schema(
    NestedField(1, "BillingAccountId", StringType(), required=False),
    NestedField(2, "SubAccountId", StringType(), required=False),
    NestedField(3, "ResourceId", StringType(), required=False),
    NestedField(4, "ResourceName", StringType(), required=False),
    NestedField(5, "ResourceType", StringType(), required=False),
    NestedField(6, "ChargePeriodStart", TimestamptzType(), required=False),
    NestedField(7, "ChargePeriodEnd", TimestamptzType(), required=False),
    NestedField(8, "BillingPeriodStart", TimestamptzType(), required=False),
    NestedField(9, "BillingPeriodEnd", TimestamptzType(), required=False),
    NestedField(10, "BilledCost", StringType(), required=False),
    NestedField(11, "EffectiveCost", StringType(), required=False),
    NestedField(12, "ListCost", StringType(), required=False),
    NestedField(13, "ContractedCost", StringType(), required=False),
    NestedField(14, "BillingCurrency", StringType(), required=False),
    NestedField(15, "ServiceName", StringType(), required=False),
    NestedField(16, "ServiceCategory", StringType(), required=False),
    NestedField(17, "ProviderName", StringType(), required=False),
    NestedField(18, "RegionId", StringType(), required=False),
    NestedField(19, "RegionName", StringType(), required=False),
    NestedField(20, "AvailabilityZone", StringType(), required=False),
    NestedField(21, "ChargeCategory", StringType(), required=False),
    NestedField(22, "ChargeDescription", StringType(), required=False),
    NestedField(23, "UsageQuantity", StringType(), required=False),
    NestedField(24, "UsageUnit", StringType(), required=False),
    NestedField(25, "PricingQuantity", StringType(), required=False),
    NestedField(26, "PricingUnit", StringType(), required=False),
    NestedField(27, "SkuId", StringType(), required=False),
    NestedField(28, "SkuPriceId", StringType(), required=False),
    NestedField(29, "CommitmentDiscountCategory", StringType(), required=False),
    NestedField(30, "CommitmentDiscountId", StringType(), required=False),
    NestedField(31, "CommitmentDiscountType", StringType(), required=False),
    NestedField(32, "Tags", StringType(), required=False),
    # Silver 파생 컬럼
    NestedField(33, "team", StringType(), required=False),
    NestedField(34, "product", StringType(), required=False),
    NestedField(35, "env", StringType(), required=False),
    NestedField(36, "cost_unit_key", StringType(), required=False),
    NestedField(37, "ChargePeriodStartUtc", TimestamptzType(), required=False),
)

_SILVER_PARTITION_SPEC = PartitionSpec(
    PartitionField(
        source_id=6,
        field_id=1000,
        transform=MonthTransform(),
        name="ChargePeriodStart_month",
    )
)


def _flatten_tags(df: pl.DataFrame) -> pl.DataFrame:
    """Tags JSON 컬럼 → team, product, env, cost_unit_key 컬럼 추가."""

    def extract_tag(tags_json: str | None, key: str) -> str:
        if tags_json is None:
            return "unknown"
        try:
            tags = json.loads(tags_json)
            return str(tags.get(key, "unknown"))
        except (json.JSONDecodeError, AttributeError):
            return "unknown"

    teams = [extract_tag(t, "team") for t in df["Tags"].to_list()]
    products = [extract_tag(t, "product") for t in df["Tags"].to_list()]
    envs = [extract_tag(t, "env") for t in df["Tags"].to_list()]
    keys = [f"{t}:{p}:{e}" for t, p, e in zip(teams, products, envs, strict=True)]

    return df.with_columns(
        [
            pl.Series("team", teams),
            pl.Series("product", products),
            pl.Series("env", envs),
            pl.Series("cost_unit_key", keys),
            pl.col("ChargePeriodStart").alias("ChargePeriodStartUtc"),
        ]
    )


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["bronze_iceberg"],
    description=(
        "Bronze Iceberg 테이블을 Polars로 읽어 Tags를 team/product/env 컬럼으로 "
        "평탄화하고 cost_unit_key를 파생한 뒤 Silver 테이블에 overwrite 적재한다."
    ),
    group_name="silver",
)
def silver_focus(
    context: AssetExecutionContext,
    iceberg_catalog: IcebergCatalogResource,
) -> None:
    """Bronze → Silver 변환.

    - Tags JSON → team, product, env 분리
    - cost_unit_key = team:product:env
    - ChargePeriodStartUtc 유지 (UTC timestamp)
    - 멱등성: overwrite
    """
    bronze_table = iceberg_catalog.load_table(_BRONZE_TABLE)
    df: pl.DataFrame = bronze_table.scan().to_polars()

    context.log.info(f"Read {len(df)} rows from {_BRONZE_TABLE}")

    # 파티션 키로 해당 월 필터링
    partition_key = context.partition_key  # "2024-01-01"
    month_str = partition_key[:7]  # "2024-01"
    df = df.filter(
        pl.col("ChargePeriodStart").dt.to_string("%Y-%m").str.starts_with(month_str)
    )

    context.log.info(f"Filtered to {len(df)} rows for {month_str}")

    df = _flatten_tags(df)


    arrow_table = df.to_arrow()

    # Silver Iceberg 스키마에 맞게 컬럼 캐스팅
    silver_iceberg_table = iceberg_catalog.ensure_table(
        _SILVER_TABLE,
        schema=_SILVER_ICEBERG_SCHEMA,
        partition_spec=_SILVER_PARTITION_SPEC,
    )
    silver_iceberg_table.overwrite(arrow_table)
    context.log.info(f"Wrote {len(df)} rows to {_SILVER_TABLE}")
