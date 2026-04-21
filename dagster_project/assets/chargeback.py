"""Chargeback Asset — 팀/제품/환경/클라우드별 비용 배부 보고서."""

from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..resources.budget_store import BudgetStoreResource
from ..resources.duckdb_io import DuckDBResource
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dim_chargeback (
    billing_month  VARCHAR        NOT NULL,
    provider       VARCHAR        NOT NULL,
    team           VARCHAR        NOT NULL,
    product        VARCHAR        NOT NULL,
    env            VARCHAR        NOT NULL,
    cost_unit_key  VARCHAR        NOT NULL,
    actual_cost    DECIMAL(18, 6) NOT NULL,
    budget_amount  DECIMAL(18, 6),
    utilization_pct DOUBLE,
    resource_count BIGINT         NOT NULL,
    PRIMARY KEY (billing_month, provider, team, product, env)
)
"""


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["gold_marts", "gold_marts_gcp", "gold_marts_azure"],
    description=(
        "fact_daily_cost를 provider/team/product/env별로 집계하여 "
        "dim_chargeback 테이블과 data/reports/chargeback_YYYYMM.csv를 생성한다."
    ),
    group_name="reporting",
)
def chargeback(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
    budget_store: BudgetStoreResource,
) -> None:
    """멀티 클라우드 비용 배부 보고서 생성.

    provider/team/product/env 단위로 집계하고 예산 데이터를 조인한다.
    멱등성: billing_month별 DELETE + INSERT.
    """
    budget_store.ensure_table()

    partition_key = context.partition_key
    month_str = partition_key[:7]
    year_month = month_str.replace("-", "")
    reports_dir = Path(_cfg.data.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    with duckdb_resource.get_connection() as conn:
        conn.execute(_CREATE_TABLE_SQL)

        has_fact = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name='fact_daily_cost'"
        ).fetchone()
        if not has_fact:
            context.log.warning("fact_daily_cost 테이블 없음 — chargeback 건너뜀")
            return

        arrow = conn.execute(f"""
            SELECT
                provider,
                team,
                product,
                env,
                cost_unit_key,
                SUM(CAST(effective_cost AS DOUBLE)) AS actual_cost,
                COUNT(DISTINCT resource_id) AS resource_count
            FROM fact_daily_cost
            WHERE STRFTIME(charge_date, '%Y-%m') = '{month_str}'
            GROUP BY provider, team, product, env, cost_unit_key
            ORDER BY actual_cost DESC
        """).arrow()

    chargeback_df: pl.DataFrame = pl.from_arrow(arrow)  # type: ignore[arg-type]
    context.log.info(f"[Chargeback] {len(chargeback_df)} groups for {month_str}")

    rows: list[dict[str, object]] = []
    for row in chargeback_df.iter_rows(named=True):
        team = str(row["team"])
        env = str(row["env"])
        actual = float(row["actual_cost"])
        budget = budget_store.get_budget(team, env)

        utilization_pct: float | None = None
        if budget and budget > 0:
            utilization_pct = actual / budget * 100.0

        rows.append({
            "billing_month": month_str,
            "provider": row["provider"],
            "team": team,
            "product": row["product"],
            "env": env,
            "cost_unit_key": row["cost_unit_key"],
            "actual_cost": actual,
            "budget_amount": budget,
            "utilization_pct": utilization_pct,
            "resource_count": int(row["resource_count"]),  # type: ignore[arg-type]
        })

    if rows:
        result_df = pl.DataFrame(rows)
        result_df.write_csv(str(reports_dir / f"chargeback_{year_month}.csv"))
        context.log.info(f"[Chargeback] Wrote CSV to reports/chargeback_{year_month}.csv")

        with duckdb_resource.get_connection() as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.execute(
                "DELETE FROM dim_chargeback WHERE billing_month = ?", [month_str]
            )
            insert_df = result_df.with_columns([
                pl.col("actual_cost").cast(pl.Float64),
                pl.col("budget_amount").cast(pl.Float64),
            ])
            conn.register("_chargeback_rows", insert_df.to_arrow())
            conn.execute("""
                INSERT INTO dim_chargeback
                    (billing_month, provider, team, product, env, cost_unit_key,
                     actual_cost, budget_amount, utilization_pct, resource_count)
                SELECT billing_month, provider, team, product, env, cost_unit_key,
                       CAST(actual_cost AS DECIMAL(18,6)),
                       CAST(budget_amount AS DECIMAL(18,6)),
                       utilization_pct,
                       resource_count
                FROM _chargeback_rows
            """)
        context.log.info(f"[Chargeback] Saved {len(rows)} rows to dim_chargeback")
    else:
        context.log.info(f"[Chargeback] No data for {month_str}")
