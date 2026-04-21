"""Savings Tracker Asset — compares recommendation estimates vs realized month-over-month savings."""

import datetime

import psycopg2.extras
from dagster import AssetExecutionContext, asset

from ..db_schema import ensure_tables
from ..resources.duckdb_io import DuckDBResource


@asset(
    deps=["cost_recommendations"],
    description=(
        "dim_cost_recommendations의 예상 절감액을 실제 전월 대비 비용 감소로 검증하여 "
        "dim_savings_realized에 저장한다."
    ),
    group_name="reporting",
)
def savings_tracker(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
) -> None:
    """Tracks realized savings by comparing estimated vs actual cost change per recommendation."""
    now = datetime.datetime.now(tz=datetime.UTC)

    with duckdb_resource.get_connection() as conn:
        ensure_tables(conn, "dim_savings_realized", "dim_cost_recommendations")

        with conn.cursor() as cur:
            # Get all distinct billing months from recommendations
            cur.execute(
                "SELECT DISTINCT billing_month FROM dim_cost_recommendations ORDER BY billing_month DESC LIMIT 12"
            )
            months = [r[0] for r in cur.fetchall()]

        if not months:
            context.log.info("No recommendations found — skipping savings tracker")
            return

        rows: list[tuple] = []

        with conn.cursor() as cur:
            for billing_month in months:
                # Get recommendations for this month
                cur.execute(
                    """
                    SELECT resource_id, team, product, env, provider,
                           recommendation_type,
                           CAST(COALESCE(estimated_savings, 0) AS DOUBLE PRECISION)
                    FROM dim_cost_recommendations
                    WHERE billing_month = %s
                    """,
                    (billing_month,),
                )
                recs = cur.fetchall()

                if not recs:
                    continue

                # Compute previous month string (e.g. 2024-03 → 2024-02)
                try:
                    month_dt = datetime.date.fromisoformat(billing_month + "-01")
                    prev_dt = (month_dt.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
                    prev_month = prev_dt.strftime("%Y-%m")
                except ValueError:
                    prev_month = None

                for resource_id, team, product, env, provider, rec_type, est_savings in recs:
                    # Look up actual costs: current month and previous month
                    cur.execute(
                        """
                        SELECT
                            CAST(SUM(CASE WHEN to_char(charge_date,'YYYY-MM') = %s
                                         THEN effective_cost ELSE 0 END) AS DOUBLE PRECISION),
                            CAST(SUM(CASE WHEN to_char(charge_date,'YYYY-MM') = %s
                                         THEN effective_cost ELSE 0 END) AS DOUBLE PRECISION)
                        FROM fact_daily_cost
                        WHERE resource_id = %s
                        """,
                        (billing_month, prev_month or billing_month, resource_id),
                    )
                    cost_row = cur.fetchone()
                    curr_cost = float(cost_row[0] or 0.0) if cost_row else 0.0
                    prev_cost = float(cost_row[1] or 0.0) if cost_row else 0.0

                    realized = prev_cost - curr_cost if prev_month else None
                    if realized is not None and realized < 0:
                        status = "cost_increased"
                    elif realized is not None and realized >= est_savings * 0.8:
                        status = "realized"
                    elif realized is not None:
                        status = "partial"
                    else:
                        status = "pending"

                    rows.append((
                        billing_month, resource_id, team, product, env, provider,
                        rec_type, est_savings, realized, prev_cost, curr_cost, status, now,
                    ))

        if not rows:
            context.log.info("No recommendation rows to process")
            return

        with conn.cursor() as cur:
            # Idempotent: DELETE for all affected months then INSERT
            months_set = list({r[0] for r in rows})
            for m in months_set:
                cur.execute(
                    "DELETE FROM dim_savings_realized WHERE billing_month = %s",
                    (m,),
                )
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO dim_savings_realized
                    (billing_month, resource_id, team, product, env, provider,
                     recommendation_type, estimated_savings, realized_savings,
                     prev_month_cost, curr_month_cost, status, computed_at)
                VALUES %s
                """,
                rows,
            )

    context.log.info(f"Savings tracker: wrote {len(rows)} rows across {len(months_set)} months")
