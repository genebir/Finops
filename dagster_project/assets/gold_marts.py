"""Gold Mart Asset — PostgreSQL로 Silver → fact/dim/view 생성 (AWS)."""


from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..resources.duckdb_io import DuckDBResource
from ..resources.iceberg_catalog import IcebergCatalogResource
from ..resources.settings_store import SettingsStoreResource
from .raw_cur import MONTHLY_PARTITIONS

_SQL_DIR = Path(__file__).parent.parent.parent / "sql" / "marts"
_cfg = load_config()

_FACT_COLUMNS = [
    "provider", "charge_date", "resource_id", "resource_name", "resource_type",
    "service_name", "service_category", "region_id",
    "team", "product", "env", "cost_unit_key",
    "effective_cost", "billed_cost", "list_cost", "record_count",
]


def _insert_fact_from_silver(
    conn: object, df: pl.DataFrame, provider: str
) -> int:
    """Silver DataFrame을 fact_daily_cost에 bulk insert한다."""
    import psycopg2.extras

    agg = df.group_by(
        "ChargePeriodStart", "ResourceId", "ResourceName", "ResourceType",
        "ServiceName", "ServiceCategory", "RegionId",
        "team", "product", "env", "cost_unit_key",
    ).agg(
        pl.col("EffectiveCost").cast(pl.Float64).sum().alias("effective_cost"),
        pl.col("BilledCost").cast(pl.Float64).sum().alias("billed_cost"),
        pl.col("ListCost").cast(pl.Float64).sum().alias("list_cost"),
        pl.len().alias("record_count"),
    ).sort("ChargePeriodStart", "effective_cost", descending=[False, True])

    if agg.is_empty():
        return 0

    rows = [
        (
            provider,
            row["ChargePeriodStart"].date() if hasattr(row["ChargePeriodStart"], "date") else row["ChargePeriodStart"],
            row["ResourceId"],
            row["ResourceName"],
            row["ResourceType"],
            row["ServiceName"],
            row["ServiceCategory"],
            row["RegionId"],
            row["team"],
            row["product"],
            row["env"],
            row["cost_unit_key"],
            row["effective_cost"],
            row["billed_cost"],
            row["list_cost"],
            row["record_count"],
        )
        for row in agg.iter_rows(named=True)
    ]

    insert_sql = (
        "INSERT INTO fact_daily_cost ("
        + ", ".join(_FACT_COLUMNS)
        + ") VALUES %s"
    )
    cur = conn.cursor()  # type: ignore[union-attr]
    psycopg2.extras.execute_values(cur, insert_sql, rows, page_size=500)
    cur.close()
    return len(rows)


def _rebuild_dim_cost_unit(conn: object) -> None:
    """dim_cost_unit을 fact_daily_cost에서 재생성한다."""
    cur = conn.cursor()  # type: ignore[union-attr]
    cur.execute("DELETE FROM dim_cost_unit")
    cur.execute("""
        INSERT INTO dim_cost_unit (cost_unit_key, team, product, env, resource_count)
        SELECT cost_unit_key, team, product, env,
               COUNT(DISTINCT resource_id)
        FROM fact_daily_cost
        GROUP BY cost_unit_key, team, product, env
        ORDER BY cost_unit_key
    """)
    cur.close()


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["silver_focus"],
    description=(
        "AWS Silver Iceberg 테이블을 PostgreSQL로 읽어 fact_daily_cost(provider='aws'), "
        "dim_cost_unit, v_top_resources_30d, v_top_cost_units_30d 마트를 생성한다."
    ),
    group_name="gold",
)
def gold_marts(
    context: AssetExecutionContext,
    iceberg_catalog: IcebergCatalogResource,
    duckdb_resource: DuckDBResource,
    settings_store: SettingsStoreResource,
) -> None:
    """Silver → Gold 집계 마트 생성 (AWS)."""
    silver_table = iceberg_catalog.load_table("focus.silver_focus")
    df: pl.DataFrame = silver_table.scan().to_polars()

    partition_key = context.partition_key
    month_str = partition_key[:7]
    df = df.filter(
        pl.col("ChargePeriodStart").dt.to_string("%Y-%m").str.starts_with(month_str)
    )
    context.log.info(f"Silver rows for {month_str}: {len(df)}")

    settings_store.ensure_table()
    lookback_days = settings_store.get_int(
        "reporting.lookback_days", _cfg.operational_defaults.reporting_lookback_days
    )
    top_resources_limit = settings_store.get_int(
        "reporting.top_resources_limit", _cfg.operational_defaults.reporting_top_resources_limit
    )
    top_cost_units_limit = settings_store.get_int(
        "reporting.top_cost_units_limit", _cfg.operational_defaults.reporting_top_cost_units_limit
    )

    with duckdb_resource.get_connection() as conn:
        cur = conn.cursor()

        cur.execute(
            "DELETE FROM fact_daily_cost WHERE provider = 'aws' AND to_char(charge_date, 'YYYY-MM') = %s",
            [month_str],
        )

        row_count = _insert_fact_from_silver(conn, df, "aws")
        context.log.info(f"fact_daily_cost (aws/{month_str}): {row_count}행")

        _rebuild_dim_cost_unit(conn)
        context.log.info("Rebuilt dim_cost_unit")

        cur.execute("DROP VIEW IF EXISTS v_top_resources_30d")
        cur.execute(f"""
            CREATE VIEW v_top_resources_30d AS
            SELECT
                resource_id, resource_name, resource_type,
                service_name, service_category, region_id,
                cost_unit_key, team, product, env,
                SUM(effective_cost) AS total_effective_cost,
                SUM(billed_cost) AS total_billed_cost,
                COUNT(DISTINCT charge_date) AS active_days
            FROM fact_daily_cost
            WHERE charge_date >= CURRENT_DATE - INTERVAL '{lookback_days} days'
            GROUP BY resource_id, resource_name, resource_type,
                     service_name, service_category, region_id,
                     cost_unit_key, team, product, env
            ORDER BY total_effective_cost DESC
            LIMIT {top_resources_limit}
        """)
        context.log.info("Rebuilt v_top_resources_30d")

        cur.execute("DROP VIEW IF EXISTS v_top_cost_units_30d")
        cur.execute(f"""
            CREATE VIEW v_top_cost_units_30d AS
            SELECT
                cost_unit_key, team, product, env,
                SUM(effective_cost) AS total_effective_cost,
                COUNT(DISTINCT resource_id) AS resource_count,
                COUNT(DISTINCT charge_date) AS active_days
            FROM fact_daily_cost
            WHERE charge_date >= CURRENT_DATE - INTERVAL '{lookback_days} days'
            GROUP BY cost_unit_key, team, product, env
            ORDER BY total_effective_cost DESC
            LIMIT {top_cost_units_limit}
        """)
        context.log.info("Rebuilt v_top_cost_units_30d")

        cur.close()
