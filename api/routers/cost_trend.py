"""Cost trend and period comparison endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read

router = APIRouter(prefix="/api/cost-trend", tags=["cost-trend"])


def _table_exists(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_cost_trend'"
        )
        return cur.fetchone() is not None


@router.get("")
def get_cost_trend(
    provider: str | None = Query(default=None),
    team: str | None = Query(default=None),
    env: str | None = Query(default=None),
    months: int = Query(default=12, ge=1, le=36),
) -> dict[str, Any]:
    """Return monthly cost trend time series."""
    with db_read() as conn:
        if not _table_exists(conn):
            return {"series": [], "months": [], "summary": {}}

        clauses: list[str] = []
        params: list[Any] = []
        if provider:
            clauses.append("provider = %s")
            params.append(provider)
        if team:
            clauses.append("team = %s")
            params.append(team)
        if env:
            clauses.append("env = %s")
            params.append(env)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT billing_month,
                       ROUND(CAST(SUM(total_cost) AS NUMERIC), 2) AS total,
                       SUM(resource_count) AS resources,
                       SUM(anomaly_count) AS anomalies
                FROM dim_cost_trend
                {where}
                GROUP BY billing_month
                ORDER BY billing_month DESC
                LIMIT %s
                """,  # noqa: S608
                params + [months],
            )
            rows = cur.fetchall()

    # Reverse to chronological
    rows = list(reversed(rows))
    series = [
        {
            "billing_month": r[0],
            "total_cost": float(r[1]),
            "resource_count": r[2],
            "anomaly_count": r[3],
        }
        for r in rows
    ]

    month_list = [s["billing_month"] for s in series]
    total_costs = [s["total_cost"] for s in series]

    mom_change = None
    if len(total_costs) >= 2 and total_costs[-2]:
        mom_change = round((total_costs[-1] - total_costs[-2]) / total_costs[-2] * 100, 1)

    return {
        "series": series,
        "months": month_list,
        "summary": {
            "latest_month": month_list[-1] if month_list else None,
            "latest_cost": total_costs[-1] if total_costs else 0,
            "mom_change_pct": mom_change,
            "avg_monthly_cost": round(sum(total_costs) / len(total_costs), 2) if total_costs else 0,
        },
    }


@router.get("/compare")
def compare_periods(
    period1: str = Query(description="YYYY-MM"),
    period2: str = Query(description="YYYY-MM"),
    team: str | None = Query(default=None),
    provider: str | None = Query(default=None),
) -> dict[str, Any]:
    """Compare costs between two billing months."""
    with db_read() as conn:
        if not _table_exists(conn):
            return {"period1": period1, "period2": period2, "items": [], "summary": {}}

        clauses = ["billing_month IN (%s, %s)"]
        params: list[Any] = [period1, period2]
        if team:
            clauses.append("team = %s")
            params.append(team)
        if provider:
            clauses.append("provider = %s")
            params.append(provider)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT billing_month, team, env, provider,
                       ROUND(CAST(SUM(total_cost) AS NUMERIC), 2) AS total
                FROM dim_cost_trend
                WHERE {" AND ".join(clauses)}
                GROUP BY billing_month, team, env, provider
                ORDER BY team, env, provider
                """,  # noqa: S608
                params,
            )
            rows = cur.fetchall()

    # Build comparison map: (team, env, provider) -> {p1: cost, p2: cost}
    cmp: dict[tuple, dict[str, float]] = {}
    for month, team_v, env_v, prov_v, cost in rows:
        key = (team_v, env_v, prov_v)
        cmp.setdefault(key, {})[month] = float(cost)

    items = []
    for (team_v, env_v, prov_v), costs in sorted(cmp.items()):
        c1 = costs.get(period1, 0.0)
        c2 = costs.get(period2, 0.0)
        change = c2 - c1
        change_pct = round(change / c1 * 100, 1) if c1 else None
        items.append({
            "team": team_v, "env": env_v, "provider": prov_v,
            "period1_cost": c1, "period2_cost": c2,
            "change": round(change, 2), "change_pct": change_pct,
        })

    total_p1 = sum(i["period1_cost"] for i in items)
    total_p2 = sum(i["period2_cost"] for i in items)
    overall_change_pct = round((total_p2 - total_p1) / total_p1 * 100, 1) if total_p1 else None

    return {
        "period1": period1, "period2": period2,
        "items": sorted(items, key=lambda x: abs(x["change"]), reverse=True),
        "summary": {
            "total_period1": round(total_p1, 2),
            "total_period2": round(total_p2, 2),
            "total_change": round(total_p2 - total_p1, 2),
            "overall_change_pct": overall_change_pct,
        },
    }
