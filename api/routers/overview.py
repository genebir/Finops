"""GET /api/overview — cost summary with optional date/provider filters."""

from fastapi import APIRouter, HTTPException, Query

from ..deps import db_read, f, tables
from ..models import OverviewResponse, TeamCost, TopResource

router = APIRouter(tags=["overview"])


@router.get("/api/overview", response_model=OverviewResponse)
def get_overview(
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None, description="YYYY-MM-DD"),
    provider: str | None = Query(None, description="aws | gcp | azure"),
) -> OverviewResponse:
    conditions: list[str] = []
    params: list[object] = []
    if start:
        conditions.append("charge_date >= %s::DATE")
        params.append(start)
    if end:
        conditions.append("charge_date <= %s::DATE")
        params.append(end)
    if provider:
        conditions.append("provider = %s")
        params.append(provider)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with db_read() as db:
        cur = db.cursor()
        cur.execute(
            f"""
            SELECT
                MIN(charge_date)::TEXT            AS period_start,
                MAX(charge_date)::TEXT            AS period_end,
                CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS total_cost,
                COUNT(DISTINCT resource_id)       AS resource_count,
                COUNT(DISTINCT charge_date)       AS active_days
            FROM fact_daily_cost
            {where}
            """,
            params,
        )
        summary = cur.fetchone()

        if not summary or summary[2] is None:
            cur.close()
            raise HTTPException(status_code=404, detail="No cost data found")

        period_start, period_end, total_cost, resource_count, active_days = summary

        cur.execute(
            f"""
            SELECT team, CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
            FROM fact_daily_cost
            {where}
            GROUP BY team ORDER BY cost DESC
            """,
            params,
        )
        team_rows = cur.fetchall()

        total = f(total_cost) or 1.0
        cost_by_team = [
            TeamCost(team=r[0], cost=f(r[1]), pct=round(f(r[1]) / total * 100, 1))
            for r in team_rows
        ]

        cur.execute(
            f"""
            SELECT resource_id, resource_name, service_name, region_id,
                   team, product, env,
                   CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost,
                   COUNT(DISTINCT charge_date) AS active_days
            FROM fact_daily_cost
            {where}
            GROUP BY resource_id, resource_name, service_name, region_id, team, product, env
            ORDER BY cost DESC LIMIT 10
            """,
            params,
        )
        resource_rows = cur.fetchall()

        top_resources = [
            TopResource(
                resource_id=r[0], resource_name=r[1], service_name=r[2],
                region_id=r[3], team=r[4], product=r[5], env=r[6],
                cost=f(r[7]), active_days=r[8],
            )
            for r in resource_rows
        ]

        anomaly_count = 0
        if "anomaly_scores" in tables(db):
            cur.execute(
                "SELECT COUNT(*) FROM anomaly_scores WHERE is_anomaly = true"
            )
            row = cur.fetchone()
            anomaly_count = row[0] if row else 0

        cur.close()

        return OverviewResponse(
            period_start=period_start, period_end=period_end,
            total_cost=round(f(total_cost), 2),
            cost_by_team=cost_by_team, top_resources=top_resources,
            anomaly_count=anomaly_count, resource_count=resource_count,
            active_days=active_days,
        )
