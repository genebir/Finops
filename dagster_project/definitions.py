"""Dagster Definitions 엔트리포인트 — 모든 asset과 resource 등록."""

from __future__ import annotations

from dagster import Definitions, load_assets_from_modules

from .assets import (
    bronze_iceberg,
    gold_marts,
    infracost_forecast,
    raw_cur,
    silver_focus,
    variance,
)
from .resources.duckdb_io import DuckDBResource
from .resources.iceberg_catalog import IcebergCatalogResource
from .resources.infracost_cli import InfracostCliResource

all_assets = load_assets_from_modules(
    [
        raw_cur,
        bronze_iceberg,
        silver_focus,
        gold_marts,
        infracost_forecast,
        variance,
    ]
)

defs = Definitions(
    assets=all_assets,
    resources={
        "iceberg_catalog": IcebergCatalogResource(),
        "duckdb_resource": DuckDBResource(),
        "infracost_cli": InfracostCliResource(),
    },
)
