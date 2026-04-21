"""Iceberg SqlCatalog Dagster 리소스."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dagster import ConfigurableResource
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.exceptions import NamespaceAlreadyExistsError, NoSuchTableError
from pyiceberg.partitioning import PartitionSpec
from pyiceberg.schema import Schema


class IcebergCatalogResource(ConfigurableResource):
    """SQLite 백엔드 SqlCatalog를 Dagster 리소스로 래핑."""

    warehouse_path: str = "data/warehouse"
    catalog_db_path: str = "data/catalog.db"

    def _get_catalog(self) -> SqlCatalog:
        Path(self.warehouse_path).mkdir(parents=True, exist_ok=True)
        Path(self.catalog_db_path).parent.mkdir(parents=True, exist_ok=True)
        from ..config import load_config  # noqa: PLC0415

        catalog_name = load_config().iceberg.catalog_name
        return SqlCatalog(
            catalog_name,
            **{
                "uri": f"sqlite:///{self.catalog_db_path}",
                "warehouse": f"file://{Path(self.warehouse_path).resolve()}",
            },
        )

    def ensure_namespace(self, name: str) -> None:
        catalog = self._get_catalog()
        try:
            catalog.create_namespace(name)
        except NamespaceAlreadyExistsError:
            pass

    def ensure_table(
        self,
        full_name: str,
        schema: Schema,
        partition_spec: PartitionSpec | None = None,
        properties: dict[str, Any] | None = None,
    ) -> Any:
        """테이블이 없으면 생성, 있으면 기존 테이블 반환."""
        catalog = self._get_catalog()
        namespace = full_name.split(".")[0]
        self.ensure_namespace(namespace)
        try:
            return catalog.load_table(full_name)
        except NoSuchTableError:
            kwargs: dict[str, Any] = {"schema": schema}
            if partition_spec is not None:
                kwargs["partition_spec"] = partition_spec
            if properties:
                kwargs["properties"] = properties
            return catalog.create_table(full_name, **kwargs)

    def load_table(self, full_name: str) -> Any:
        return self._get_catalog().load_table(full_name)
