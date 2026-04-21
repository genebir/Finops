"""Chargeback Asset — 팀/제품/환경/클라우드별 비용 배부 보고서."""

from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..resources.budget_store import BudgetStoreResource
from ..resources.duckdb_io import DuckDBResource
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()


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
    """멀티 클라우드 비용 배부 보고서 생성."""
    budget_store.ensure_table()

    partition_key = context.partition_key
    month_str = partition_key[:7]
    year_month = month_str.replace("-", "")
    reports_dir = Path(_cfg.data.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    with duckdb_resource.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='fact_daily_cost'"
        )
        if not cur.fetchone():
            context.log.warning("fact_daily_cost 테이블 없음 — chargeback 건너뜀")
            cur.close()
            return

        cur.execute("""
            SELECT provider, team, product, env, cost_unit_key,
                   SUM(CAST(effective_cost AS DOUBLE PRECISION)) AS actual_cost,
                   COUNT(DISTINCT resource_id) AS resource_count
            FROM fact_daily_cost
            WHERE to_char(charge_date, 'YYYY-MM') = %s
            GROUP BY provider, team, product, env, cost_unit_key
            ORDER BY actual_cost DESC
        """, [month_str])
        chargeback_rows = cur.fetchall()
        cur.close()

    context.log.info(f"[Chargeback] {len(chargeback_rows)} groups for {month_str}")

    rows: list[dict[str, object]] = []
    for provider, team, product, env, cost_unit_key, actual, resource_count in chargeback_rows:
        budget = budget_store.get_budget(team, env)
        utilization_pct: float | None = None
        if budget and budget > 0:
            utilization_pct = float(actual) / budget * 100.0

        rows.append({
            "billing_month": month_str, "provider": provider,
            "team": team, "product": product, "env": env,
            "cost_unit_key": cost_unit_key, "actual_cost": float(actual),
            "budget_amount": budget, "utilization_pct": utilization_pct,
            "resource_count": int(resource_count),
        })

    if rows:
        result_df = pl.DataFrame(rows)
        result_df.write_csv(str(reports_dir / f"chargeback_{year_month}.csv"))
        context.log.info(f"[Chargeback] Wrote CSV to reports/chargeback_{year_month}.csv")

        import psycopg2.extras

        with duckdb_resource.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM dim_chargeback WHERE billing_month = %s", [month_str])
            values = [
                (r["billing_month"], r["provider"], r["team"], r["product"], r["env"],
                 r["cost_unit_key"], r["actual_cost"], r["budget_amount"],
                 r["utilization_pct"], r["resource_count"])
                for r in rows
            ]
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO dim_chargeback
                    (billing_month, provider, team, product, env, cost_unit_key,
                     actual_cost, budget_amount, utilization_pct, resource_count)
                VALUES %s
                """,
                values, page_size=500,
            )
            cur.close()
        context.log.info(f"[Chargeback] Saved {len(rows)} rows to dim_chargeback")
    else:
        context.log.info(f"[Chargeback] No data for {month_str}")
