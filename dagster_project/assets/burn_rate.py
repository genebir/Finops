"""Burn Rate Asset — month-to-date cost velocity and projected end-of-month spend."""

import calendar
import datetime

import psycopg2.extras
from dagster import AssetExecutionContext, asset

from ..db_schema import ensure_tables
from ..resources.duckdb_io import DuckDBResource
from ..resources.settings_store import SettingsStoreResource

_BURN_DDL = """
CREATE TABLE IF NOT EXISTS dim_burn_rate (
    billing_month        VARCHAR          NOT NULL,
    team                 VARCHAR          NOT NULL,
    env                  VARCHAR          NOT NULL,
    days_elapsed         INTEGER          NOT NULL,
    days_in_month        INTEGER          NOT NULL,
    mtd_cost             DOUBLE PRECISION NOT NULL,
    daily_avg            DOUBLE PRECISION NOT NULL,
    projected_eom        DOUBLE PRECISION NOT NULL,
    budget_amount        DOUBLE PRECISION,
    projected_utilization DOUBLE PRECISION,
    status               VARCHAR          NOT NULL,
    refreshed_at         TIMESTAMPTZ      NOT NULL
)
"""


def _compute_burn(conn, month_str: str, warn_pct: float, crit_pct: float) -> list[dict]:
    year, month = int(month_str[:4]), int(month_str[5:7])
    days_in_month = calendar.monthrange(year, month)[1]
    today = datetime.date.today()
    if today.year == year and today.month == month:
        days_elapsed = today.day
    else:
        days_elapsed = days_in_month

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT team, env, CAST(SUM(effective_cost) AS DOUBLE PRECISION) as mtd
            FROM fact_daily_cost
            WHERE to_char(charge_date, 'YYYY-MM') = %s
            GROUP BY team, env
            """,
            (month_str,),
        )
        rows = cur.fetchall()

    results = []
    for team, env, mtd in rows:
        daily_avg = mtd / days_elapsed if days_elapsed else 0.0
        projected = daily_avg * days_in_month

        # Lookup budget
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT CAST(budget_amount AS DOUBLE PRECISION)
                FROM dim_budget
                WHERE (team = %s OR team = '*')
                  AND (env = %s OR env = '*')
                ORDER BY
                  CASE WHEN team = %s THEN 0 ELSE 1 END,
                  CASE WHEN env = %s THEN 0 ELSE 1 END
                LIMIT 1
                """,
                (team, env, team, env),
            )
            br = cur.fetchone()
        budget = br[0] if br else None

        proj_util = (projected / budget * 100.0) if budget else None

        if proj_util is None:
            status = "no_budget"
        elif proj_util >= crit_pct:
            status = "critical"
        elif proj_util >= warn_pct:
            status = "warning"
        else:
            status = "on_track"

        results.append({
            "billing_month": month_str,
            "team": team,
            "env": env,
            "days_elapsed": days_elapsed,
            "days_in_month": days_in_month,
            "mtd_cost": mtd,
            "daily_avg": daily_avg,
            "projected_eom": projected,
            "budget_amount": budget,
            "projected_utilization": proj_util,
            "status": status,
            "refreshed_at": datetime.datetime.now(datetime.UTC),
        })

    return results


@asset(
    deps=["gold_marts", "gold_marts_gcp", "gold_marts_azure"],
    description=(
        "Computes month-to-date cost velocity, daily average, and projected end-of-month spend "
        "for each (team, env) and stores results in dim_burn_rate."
    ),
    group_name="reporting",
)
def burn_rate(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
    settings_store: SettingsStoreResource,
) -> None:
    """Calculate burn rate for current and previous months."""
    settings_store.ensure_table()

    warn_pct = settings_store.get_float("budget.alert_threshold_pct", 80.0)
    crit_pct = settings_store.get_float("budget.over_threshold_pct", 100.0)

    today = datetime.date.today()
    months = [
        today.strftime("%Y-%m"),
        (today.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m"),
    ]

    with duckdb_resource.get_connection() as conn:
        ensure_tables(conn, "dim_burn_rate", "pipeline_run_log")

        with conn.cursor() as cur:
            cur.execute(_BURN_DDL)

        all_rows: list[dict] = []
        for month_str in months:
            rows = _compute_burn(conn, month_str, warn_pct, crit_pct)
            all_rows.extend(rows)

        if not all_rows:
            context.log.info("burn_rate: no data found for months %s", months)
            return

        with conn.cursor() as cur:
            for m in months:
                cur.execute("DELETE FROM dim_burn_rate WHERE billing_month = %s", (m,))

            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO dim_burn_rate
                  (billing_month, team, env, days_elapsed, days_in_month,
                   mtd_cost, daily_avg, projected_eom, budget_amount,
                   projected_utilization, status, refreshed_at)
                VALUES %s
                """,
                [
                    (
                        r["billing_month"], r["team"], r["env"],
                        r["days_elapsed"], r["days_in_month"],
                        r["mtd_cost"], r["daily_avg"], r["projected_eom"],
                        r["budget_amount"], r["projected_utilization"],
                        r["status"], r["refreshed_at"],
                    )
                    for r in all_rows
                ],
            )

    critical = sum(1 for r in all_rows if r["status"] == "critical")
    context.log.info(
        "burn_rate: %d rows written, %d critical projections", len(all_rows), critical
    )
