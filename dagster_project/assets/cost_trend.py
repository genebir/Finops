"""Cost Trend Asset — monthly cost rollups for trend analysis."""

import datetime

import psycopg2.extras
from dagster import AssetExecutionContext, asset

from ..resources.duckdb_io import DuckDBResource

_TREND_DDL = """
CREATE TABLE IF NOT EXISTS dim_cost_trend (
    billing_month   VARCHAR          NOT NULL,
    provider        VARCHAR          NOT NULL,
    team            VARCHAR          NOT NULL,
    env             VARCHAR          NOT NULL,
    service_name    VARCHAR,
    total_cost      DOUBLE PRECISION NOT NULL,
    resource_count  BIGINT           NOT NULL,
    anomaly_count   INTEGER          NOT NULL DEFAULT 0,
    computed_at     TIMESTAMPTZ      NOT NULL,
    PRIMARY KEY (billing_month, provider, team, env, COALESCE(service_name, ''))
)
"""

# Can't use COALESCE in PK — use separate index approach
_TREND_DDL_V2 = """
CREATE TABLE IF NOT EXISTS dim_cost_trend (
    billing_month   VARCHAR          NOT NULL,
    provider        VARCHAR          NOT NULL,
    team            VARCHAR          NOT NULL,
    env             VARCHAR          NOT NULL,
    service_name    VARCHAR          NOT NULL DEFAULT '',
    total_cost      DOUBLE PRECISION NOT NULL,
    resource_count  BIGINT           NOT NULL,
    anomaly_count   INTEGER          NOT NULL DEFAULT 0,
    computed_at     TIMESTAMPTZ      NOT NULL
)
"""


@asset(
    deps=["gold_marts", "gold_marts_gcp", "gold_marts_azure", "anomaly_detection"],
    description=(
        "Computes monthly cost rollups per (provider, team, env, service) "
        "for trend analysis and period comparison."
    ),
    group_name="reporting",
)
def cost_trend(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
) -> None:
    """Build monthly cost trend data for all available months."""
    now = datetime.datetime.now(datetime.UTC)

    with duckdb_resource.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_TREND_DDL_V2)

        # Get all available months
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT to_char(charge_date, 'YYYY-MM') FROM fact_daily_cost ORDER BY 1"
            )
            months = [r[0] for r in cur.fetchall()]

        if not months:
            context.log.info("cost_trend: no data in fact_daily_cost")
            return

        for month in months:
            # Cost rollup
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT provider, team, env,
                           COALESCE(service_name, '') AS service_name,
                           CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS total_cost,
                           COUNT(DISTINCT resource_id) AS resource_count
                    FROM fact_daily_cost
                    WHERE to_char(charge_date, 'YYYY-MM') = %s
                    GROUP BY provider, team, env, COALESCE(service_name, '')
                    """,
                    (month,),
                )
                cost_rows = cur.fetchall()

            # Anomaly count per (team, env) — no provider in anomaly_scores
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT team, env, COUNT(*) as cnt
                    FROM anomaly_scores
                    WHERE to_char(charge_date, 'YYYY-MM') = %s AND is_anomaly
                    GROUP BY team, env
                    """,
                    (month,),
                )
                anomaly_map: dict[tuple, int] = {(r[0], r[1]): r[2] for r in cur.fetchall()}

            records = [
                (
                    month, provider, team, env, svc,
                    total_cost, resource_count,
                    anomaly_map.get((team, env), 0),
                    now,
                )
                for provider, team, env, svc, total_cost, resource_count in cost_rows
            ]

            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM dim_cost_trend
                    WHERE billing_month = %s
                    """,
                    (month,),
                )
                if records:
                    psycopg2.extras.execute_values(
                        cur,
                        """
                        INSERT INTO dim_cost_trend
                          (billing_month, provider, team, env, service_name,
                           total_cost, resource_count, anomaly_count, computed_at)
                        VALUES %s
                        """,
                        records,
                    )

    context.log.info(
        "cost_trend: computed rollups for %d months", len(months)
    )
