"""Bronze Iceberg Azure Asset — Azure FOCUS 레코드를 Iceberg 테이블에 적재."""


import pyarrow as pa
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..resources.iceberg_catalog import IcebergCatalogResource
from ..schemas.focus_v1 import FOCUS_PYARROW_SCHEMA, FocusRecord
from .bronze_iceberg import _ICEBERG_SCHEMA, _PARTITION_SPEC
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["raw_cur_azure"],
    description="Azure FOCUS 레코드를 Iceberg focus.bronze_cur_azure 테이블에 월별 파티션으로 overwrite 적재한다.",
    group_name="bronze",
)
def bronze_iceberg_azure(
    context: AssetExecutionContext,
    raw_cur_azure: list[FocusRecord],
    iceberg_catalog: IcebergCatalogResource,
) -> None:
    """Azure raw_cur 레코드를 PyArrow Table로 변환 후 Iceberg에 overwrite 적재.

    멱등성: 동일 월 파티션에 대해 항상 overwrite.
    """
    table_name = _cfg.azure_iceberg.bronze_table
    context.log.info(f"[Azure] Writing {len(raw_cur_azure)} records to {table_name}")

    rows = [r.to_pyarrow_row() for r in raw_cur_azure]
    table = pa.Table.from_pylist(rows, schema=FOCUS_PYARROW_SCHEMA)

    iceberg_table = iceberg_catalog.ensure_table(
        table_name,
        schema=_ICEBERG_SCHEMA,
        partition_spec=_PARTITION_SPEC,
    )
    iceberg_table.overwrite(table)
    context.log.info(f"[Azure] Overwrote {len(raw_cur_azure)} rows into {table_name}")
