"""GET /api/cost-heatmap — daily cost matrix for heatmap visualization."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/cost-heatmap", tags=["cost-heatmap"])


@router.get("")
def cost_heatmap(
    billing_month: str | None = Query(None, description="YYYY-MM"),
    provider: str | None = Query(None),
    team: str | None = Query(None),
) -> dict[str, Any]:
    """Returns a daily cost matrix: rows=teams, cols=dates, values=cost."""
    with db_read() as conn:
        with conn.cursor() as cur:
            if billing_month:
                month = billing_month
            else:
                cur.execute("SELECT to_char(MAX(charge_date),'YYYY-MM') FROM fact_daily_cost")
                row = cur.fetchone()
                month = row[0] if row and row[0] else "2024-01"

            filters = ["to_char(charge_date, 'YYYY-MM') = %s"]
            params: list[Any] = [month]
            if provider:
                filters.append("provider = %s")
                params.append(provider)
            if team:
                filters.append("team = %s")
                params.append(team)
            where = "WHERE " + " AND ".join(filters)

            cur.execute(
                f"""
                SELECT charge_date::TEXT,
                       team,
                       CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                {where}
                GROUP BY charge_date, team
                ORDER BY charge_date, team
                """,
                params,
            )
            rows = cur.fetchall()

    # Build matrix
    dates_set: set[str] = set()
    teams_set: set[str] = set()
    cell: dict[tuple[str, str], float] = {}
    for date_str, team_name, cost in rows:
        dates_set.add(date_str)
        teams_set.add(team_name)
        cell[(date_str, team_name)] = round(f(cost), 2)

    dates = sorted(dates_set)
    teams = sorted(teams_set)

    matrix = [
        {
            "team": t,
            "values": [cell.get((d, t), 0.0) for d in dates],
        }
        for t in teams
    ]

    max_cost = max((v for row in matrix for v in row["values"]), default=0.0)

    return {
        "billing_month": month,
        "dates": dates,
        "teams": teams,
        "matrix": matrix,
        "max_cost": round(max_cost, 2),
    }
