"""Bronze Iceberg Asset — FOCUS 레코드를 Iceberg 테이블에 적재."""


import pyarrow as pa
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
from ..schemas.focus_v1 import FOCUS_PYARROW_SCHEMA, FocusRecord
from .raw_cur import MONTHLY_PARTITIONS

_TABLE_NAME = "focus.bronze_cur"

# PyArrow nullable 컬럼과 호환되도록 required=False로 통일
_ICEBERG_SCHEMA = Schema(
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
)

_PARTITION_SPEC = PartitionSpec(
    PartitionField(source_id=6, field_id=1000, transform=MonthTransform(), name="ChargePeriodStart_month")
)


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["raw_cur"],
    description="FOCUS 레코드를 Iceberg focus.bronze_cur 테이블에 월별 파티션으로 overwrite 적재한다.",
    group_name="bronze",
)
def bronze_iceberg(
    context: AssetExecutionContext,
    raw_cur: list[FocusRecord],
    iceberg_catalog: IcebergCatalogResource,
) -> None:
    """raw_cur 레코드를 PyArrow Table로 변환 후 Iceberg에 overwrite 적재.

    멱등성: 동일 월 파티션에 대해 항상 overwrite (append 금지).
    """
    context.log.info(f"Writing {len(raw_cur)} records to {_TABLE_NAME}")

    rows = [r.to_pyarrow_row() for r in raw_cur]
    table = pa.Table.from_pylist(rows, schema=FOCUS_PYARROW_SCHEMA)

    iceberg_table = iceberg_catalog.ensure_table(
        _TABLE_NAME,
        schema=_ICEBERG_SCHEMA,
        partition_spec=_PARTITION_SPEC,
    )

    iceberg_table.overwrite(table)
    context.log.info(f"Overwrote {len(raw_cur)} rows into {_TABLE_NAME}")
