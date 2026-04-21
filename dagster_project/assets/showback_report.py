"""Showback Report Asset — monthly per-team cost summary for stakeholder visibility."""

import datetime
import json

import psycopg2.extras
from dagster import AssetExecutionContext, asset

from ..resources.duckdb_io import DuckDBResource

_SHOWBACK_DDL = """
CREATE TABLE IF NOT EXISTS dim_showback_report (
    id              BIGSERIAL        PRIMARY KEY,
    billing_month   VARCHAR          NOT NULL,
    team            VARCHAR          NOT NULL,
    total_cost      DOUBLE PRECISION NOT NULL,
    budget_amount   DOUBLE PRECISION,
    utilization_pct DOUBLE PRECISION,
    anomaly_count   INTEGER          NOT NULL DEFAULT 0,
    top_services    JSONB,
    top_resources   JSONB,
    generated_at    TIMESTAMPTZ      NOT NULL
)
"""


def _json_or_null(obj) -> str | None:
    if obj is None:
        return None
    return json.dumps(obj)


@asset(
    deps=["gold_marts", "gold_marts_gcp", "gold_marts_azure", "budget_alerts", "anomaly_detection"],
    description=(
        "Generates monthly per-team showback reports from fact_daily_cost, "
        "dim_budget_status, and anomaly_scores, stored in dim_showback_report."
    ),
    group_name="reporting",
)
def showback_report(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
) -> None:
    """Build showback reports for current and previous month."""
    now = datetime.datetime.now(datetime.UTC)
    today = datetime.date.today()
    months = [
        today.strftime("%Y-%m"),
        (today.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m"),
    ]

    with duckdb_resource.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SHOWBACK_DDL)

        for month in months:
            # Total cost per team
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT team,
                           CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS total_cost
                    FROM fact_daily_cost
                    WHERE to_char(charge_date, 'YYYY-MM') = %s
                    GROUP BY team
                    ORDER BY total_cost DESC
                    """,
                    (month,),
                )
                team_costs = {r[0]: r[1] for r in cur.fetchall()}

            if not team_costs:
                continue

            # Budget status
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT team, CAST(budget_amount AS DOUBLE PRECISION), utilization_pct
                    FROM dim_budget_status
                    WHERE billing_month = %s
                    """,
                    (month,),
                )
                budget_map: dict[str, tuple[float, float]] = {
                    r[0]: (r[1], r[2]) for r in cur.fetchall()
                }

            # Anomaly count per team
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT team, COUNT(*) as cnt
                    FROM anomaly_scores
                    WHERE to_char(charge_date, 'YYYY-MM') = %s AND is_anomaly
                    GROUP BY team
                    """,
                    (month,),
                )
                anomaly_map: dict[str, int] = {r[0]: r[1] for r in cur.fetchall()}

            # Top 3 services per team
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT team, service_name,
                           ROUND(CAST(SUM(effective_cost) AS NUMERIC), 2) AS svc_cost
                    FROM fact_daily_cost
                    WHERE to_char(charge_date, 'YYYY-MM') = %s AND service_name IS NOT NULL
                    GROUP BY team, service_name
                    ORDER BY team, svc_cost DESC
                    """,
                    (month,),
                )
                svc_rows = cur.fetchall()

            services_by_team: dict[str, list[dict]] = {}
            for team, svc, cost in svc_rows:
                services_by_team.setdefault(team, [])
                if len(services_by_team[team]) < 3:
                    services_by_team[team].append({"service": svc, "cost": float(cost)})

            # Top 3 resources per team
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT team, resource_id, resource_name,
                           ROUND(CAST(SUM(effective_cost) AS NUMERIC), 2) AS res_cost
                    FROM fact_daily_cost
                    WHERE to_char(charge_date, 'YYYY-MM') = %s
                    GROUP BY team, resource_id, resource_name
                    ORDER BY team, res_cost DESC
                    """,
                    (month,),
                )
                res_rows = cur.fetchall()

            resources_by_team: dict[str, list[dict]] = {}
            for team, rid, rname, cost in res_rows:
                resources_by_team.setdefault(team, [])
                if len(resources_by_team[team]) < 3:
                    resources_by_team[team].append({
                        "resource_id": rid,
                        "resource_name": rname,
                        "cost": float(cost),
                    })

            # Build records
            records = []
            for team, total_cost in team_costs.items():
                budget_amount, utilization_pct = budget_map.get(team, (None, None))
                records.append((
                    month, team, total_cost, budget_amount, utilization_pct,
                    anomaly_map.get(team, 0),
                    json.dumps(services_by_team.get(team, [])),
                    json.dumps(resources_by_team.get(team, [])),
                    now,
                ))

            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM dim_showback_report WHERE billing_month = %s", (month,)
                )
                if records:
                    psycopg2.extras.execute_values(
                        cur,
                        """
                        INSERT INTO dim_showback_report
                          (billing_month, team, total_cost, budget_amount, utilization_pct,
                           anomaly_count, top_services, top_resources, generated_at)
                        VALUES %s
                        """,
                        records,
                    )

            context.log.info(
                "showback_report: %d team reports written for %s", len(records), month
            )
