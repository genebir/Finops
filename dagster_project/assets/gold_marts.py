"""Gold Mart Asset — DuckDB로 Silver → fact/dim/view 생성."""


from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..resources.duckdb_io import DuckDBResource
from ..resources.iceberg_catalog import IcebergCatalogResource
from .raw_cur import MONTHLY_PARTITIONS

_SQL_DIR = Path(__file__).parent.parent.parent / "sql" / "marts"


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["silver_focus"],
    description=(
        "Silver Iceberg 테이블을 DuckDB로 읽어 fact_daily_cost, dim_cost_unit, "
        "v_top_resources_30d, v_top_cost_units_30d 마트를 생성한다."
    ),
    group_name="gold",
)
def gold_marts(
    context: AssetExecutionContext,
    iceberg_catalog: IcebergCatalogResource,
    duckdb_resource: DuckDBResource,
) -> None:
    """Silver → Gold 집계 마트 생성.

    DuckDB에서 Iceberg 데이터를 직접 읽기 위해 PyIceberg로 읽어 Polars 경유 적재한다.
    CREATE OR REPLACE TABLE/VIEW로 멱등성을 보장한다.
    """
    silver_table = iceberg_catalog.load_table("focus.silver_focus")
    df: pl.DataFrame = silver_table.scan().to_polars()

    partition_key = context.partition_key  # "2024-01-01"
    month_str = partition_key[:7]
    df = df.filter(
        pl.col("ChargePeriodStart").dt.to_string("%Y-%m").str.starts_with(month_str)
    )
    context.log.info(f"Silver rows for {month_str}: {len(df)}")

    with duckdb_resource.get_connection() as conn:
        conn.register("silver_focus", df.to_arrow())

        fact_sql = (_SQL_DIR / "fact_daily_cost.sql").read_text()
        conn.execute(fact_sql)
        context.log.info("Created fact_daily_cost")

        dim_sql = (_SQL_DIR / "dim_cost_unit.sql").read_text()
        conn.execute(dim_sql)
        context.log.info("Created dim_cost_unit")

        top_res_sql = (_SQL_DIR / "v_top_resources_30d.sql").read_text()
        conn.execute(top_res_sql)
        context.log.info("Created v_top_resources_30d")

        conn.execute("""
            CREATE OR REPLACE VIEW v_top_cost_units_30d AS
            SELECT
                cost_unit_key,
                team,
                product,
                env,
                SUM(effective_cost) AS total_effective_cost,
                COUNT(DISTINCT resource_id) AS resource_count,
                COUNT(DISTINCT charge_date) AS active_days
            FROM fact_daily_cost
            WHERE charge_date >= CURRENT_DATE - INTERVAL '30' DAY
            GROUP BY cost_unit_key, team, product, env
            ORDER BY total_effective_cost DESC
            LIMIT 10
        """)
        context.log.info("Created v_top_cost_units_30d")

        row_count = conn.execute("SELECT COUNT(*) FROM fact_daily_cost").fetchone()
        context.log.info(f"fact_daily_cost total rows: {row_count[0] if row_count else 0}")
