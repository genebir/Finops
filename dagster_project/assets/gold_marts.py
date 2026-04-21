"""Gold Mart Asset — DuckDB로 Silver → fact/dim/view 생성 (AWS)."""


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

_INSERT_FACT_SQL = """
INSERT INTO fact_daily_cost
SELECT
    '{provider}' AS provider,
    CAST(strftime(ChargePeriodStart, '%Y-%m-%d') AS DATE) AS charge_date,
    ResourceId                                             AS resource_id,
    ResourceName                                           AS resource_name,
    ResourceType                                           AS resource_type,
    ServiceName                                            AS service_name,
    ServiceCategory                                        AS service_category,
    RegionId                                               AS region_id,
    team,
    product,
    env,
    cost_unit_key,
    SUM(CAST(EffectiveCost AS DECIMAL(18, 6)))             AS effective_cost,
    SUM(CAST(BilledCost AS DECIMAL(18, 6)))                AS billed_cost,
    SUM(CAST(ListCost AS DECIMAL(18, 6)))                  AS list_cost,
    COUNT(*)                                               AS record_count
FROM {silver_view}
GROUP BY
    charge_date, resource_id, resource_name, resource_type,
    service_name, service_category, region_id,
    team, product, env, cost_unit_key
ORDER BY charge_date, effective_cost DESC
"""


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["silver_focus"],
    description=(
        "AWS Silver Iceberg 테이블을 DuckDB로 읽어 fact_daily_cost(provider='aws'), "
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
    """Silver → Gold 집계 마트 생성 (AWS).

    fact_daily_cost는 provider 컬럼으로 멀티 클라우드 데이터를 단일 테이블에 관리한다.
    파티션 키별 DELETE + INSERT로 멱등성을 보장한다.
    """
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
        conn.register("silver_focus", df.to_arrow())

        # CREATE TABLE IF NOT EXISTS (멀티 클라우드 통합 테이블)
        fact_ddl = (_SQL_DIR / "fact_daily_cost.sql").read_text()
        conn.execute(fact_ddl)
        # 기존 테이블에 provider 컬럼이 없으면 추가 (마이그레이션)
        conn.execute(
            "ALTER TABLE fact_daily_cost ADD COLUMN IF NOT EXISTS provider VARCHAR DEFAULT 'aws'"
        )

        # 이 파티션의 AWS 데이터만 교체
        conn.execute(
            "DELETE FROM fact_daily_cost WHERE provider = 'aws' AND STRFTIME(charge_date, '%Y-%m') = ?",
            [month_str],
        )
        conn.execute(_INSERT_FACT_SQL.format(provider="aws", silver_view="silver_focus"))
        row_count = conn.execute(
            "SELECT COUNT(*) FROM fact_daily_cost WHERE provider = 'aws' AND STRFTIME(charge_date, '%Y-%m') = ?",
            [month_str],
        ).fetchone()
        context.log.info(f"fact_daily_cost (aws/{month_str}): {row_count[0] if row_count else 0}행")

        # dim_cost_unit: 전체 데이터에서 재생성
        dim_sql = (_SQL_DIR / "dim_cost_unit.sql").read_text()
        conn.execute(dim_sql)
        context.log.info("Rebuilt dim_cost_unit")

        top_res_sql = (
            (_SQL_DIR / "v_top_resources_30d.sql")
            .read_text()
            .replace("{{lookback_days}}", str(lookback_days))
            .replace("{{top_resources_limit}}", str(top_resources_limit))
        )
        conn.execute(top_res_sql)
        context.log.info("Rebuilt v_top_resources_30d")

        conn.execute(f"""
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
            WHERE charge_date >= CURRENT_DATE - INTERVAL {lookback_days} DAY
            GROUP BY cost_unit_key, team, product, env
            ORDER BY total_effective_cost DESC
            LIMIT {top_cost_units_limit}
        """)
        context.log.info("Rebuilt v_top_cost_units_30d")
