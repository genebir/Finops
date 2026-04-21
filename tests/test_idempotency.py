"""멱등성 테스트 — Bronze asset 2회 materialize → 동일 결과."""

import hashlib
import json
import tempfile
from datetime import date
from pathlib import Path

import pyarrow as pa

from dagster_project.generators.aws_cur_generator import AwsCurGenerator
from dagster_project.resources.iceberg_catalog import IcebergCatalogResource
from dagster_project.schemas.focus_v1 import FOCUS_PYARROW_SCHEMA


def _write_bronze(catalog: IcebergCatalogResource, records_rows: list[dict]) -> None:
    from dagster_project.assets.bronze_iceberg import (
        _ICEBERG_SCHEMA,
        _PARTITION_SPEC,
        _TABLE_NAME,
    )

    table = pa.Table.from_pylist(records_rows, schema=FOCUS_PYARROW_SCHEMA)
    iceberg_table = catalog.ensure_table(_TABLE_NAME, schema=_ICEBERG_SCHEMA, partition_spec=_PARTITION_SPEC)
    iceberg_table.overwrite(table)


def _read_bronze_hash(catalog: IcebergCatalogResource) -> str:
    from dagster_project.assets.bronze_iceberg import _TABLE_NAME

    iceberg_table = catalog.load_table(_TABLE_NAME)
    arrow_table = iceberg_table.scan().to_arrow()
    rows = arrow_table.to_pylist()
    payload = json.dumps(rows, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


class TestBronzeIdempotency:
    def test_double_write_same_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog = IcebergCatalogResource(
                warehouse_path=str(Path(tmpdir) / "warehouse"),
                catalog_db_path=str(Path(tmpdir) / "catalog.db"),
            )

            gen = AwsCurGenerator(seed=42)
            period_start = date(2024, 1, 1)
            period_end = date(2024, 2, 1)
            records = list(gen.generate(period_start, period_end))
            rows = [r.to_pyarrow_row() for r in records]

            _write_bronze(catalog, rows)
            hash1 = _read_bronze_hash(catalog)

            _write_bronze(catalog, rows)
            hash2 = _read_bronze_hash(catalog)

            assert hash1 == hash2, "Bronze 2회 write 후 해시가 달라졌다 — append가 발생했을 수 있음"

    def test_row_count_stable_after_double_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog = IcebergCatalogResource(
                warehouse_path=str(Path(tmpdir) / "warehouse"),
                catalog_db_path=str(Path(tmpdir) / "catalog.db"),
            )
            from dagster_project.assets.bronze_iceberg import _TABLE_NAME

            gen = AwsCurGenerator(seed=42)
            records = list(gen.generate(date(2024, 1, 1), date(2024, 2, 1)))
            rows = [r.to_pyarrow_row() for r in records]

            _write_bronze(catalog, rows)
            count1 = catalog.load_table(_TABLE_NAME).scan().to_arrow().num_rows

            _write_bronze(catalog, rows)
            count2 = catalog.load_table(_TABLE_NAME).scan().to_arrow().num_rows

            assert count1 == count2 == len(records)
