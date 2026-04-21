"""Budget Forecast Asset — linear EOM projection from MTD spend with simple confidence band."""

import calendar
import datetime
import math

import psycopg2.extras
from dagster import AssetExecutionContext, asset

from ..db_schema import ensure_tables
from ..resources.duckdb_io import DuckDBResource
from ..resources.budget_store import BudgetStoreResource


@asset(
    deps=["gold_marts", "gold_marts_gcp", "gold_marts_azure"],
    description=(
        "MTD 실제 비용을 기반으로 선형 외삽으로 월말 예상 비용과 신뢰 구간을 계산하여 "
        "dim_budget_forecast에 저장한다."
    ),
    group_name="reporting",
)
def budget_forecast(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
    budget_store: BudgetStoreResource,
) -> None:
    """Computes linear EOM projection per (team, env) from MTD daily cost."""
    now = datetime.datetime.now(tz=datetime.UTC)

    with duckdb_resource.get_connection() as conn:
        ensure_tables(conn, "dim_budget_forecast")

        with conn.cursor() as cur:
            # Get latest billing month
            cur.execute("SELECT to_char(MAX(charge_date),'YYYY-MM') FROM fact_daily_cost")
            row = cur.fetchone()
            if not row or not row[0]:
                context.log.info("No fact data — skipping budget_forecast")
                return
            billing_month = row[0]

        year, month = int(billing_month[:4]), int(billing_month[5:7])
        days_in_month = calendar.monthrange(year, month)[1]

        with conn.cursor() as cur:
            # MTD cost and count of distinct days per (team, env)
            cur.execute(
                """
                SELECT team, env,
                       CAST(SUM(effective_cost) AS DOUBLE PRECISION)   AS mtd_cost,
                       COUNT(DISTINCT charge_date)                      AS days_elapsed
                FROM fact_daily_cost
                WHERE to_char(charge_date,'YYYY-MM') = %s
                GROUP BY team, env
                """,
                (billing_month,),
            )
            team_rows = cur.fetchall()

        if not team_rows:
            context.log.info("No MTD data found")
            return

        rows: list[tuple] = []
        for team, env, mtd_cost, days_elapsed in team_rows:
            if days_elapsed == 0:
                continue
            daily_avg = mtd_cost / days_elapsed
            projected_eom = daily_avg * days_in_month

            # Simple ±20% confidence band (wider when fewer days elapsed)
            uncertainty = 0.20 * (1 - days_elapsed / days_in_month)
            lower_bound = projected_eom * (1 - uncertainty)
            upper_bound = projected_eom * (1 + uncertainty)

            budget_amount = budget_store.get_budget(team, env)
            projected_pct = (projected_eom / budget_amount * 100) if budget_amount else None

            if projected_pct is not None and projected_pct >= 100:
                risk_level = "over"
            elif projected_pct is not None and projected_pct >= 80:
                risk_level = "warning"
            else:
                risk_level = "normal"

            rows.append((
                billing_month, team, env, days_elapsed, days_in_month,
                mtd_cost, projected_eom, lower_bound, upper_bound,
                budget_amount, projected_pct, risk_level, now,
            ))

        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM dim_budget_forecast WHERE billing_month = %s",
                (billing_month,),
            )
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO dim_budget_forecast
                    (billing_month, team, env, days_elapsed, days_in_month,
                     mtd_cost, projected_eom, lower_bound, upper_bound,
                     budget_amount, projected_pct, risk_level, computed_at)
                VALUES %s
                """,
                rows,
            )

    context.log.info(
        f"Budget forecast: wrote {len(rows)} rows for {billing_month} "
        f"({days_in_month} days in month, latest elapsed: {max(r[3] for r in rows)} days)"
    )
