"""GET /api/env-breakdown — cost by environment with team cross-tab."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/env-breakdown", tags=["env-breakdown"])


@router.get("")
def env_breakdown(
    billing_month: str | None = Query(None),
    provider: str | None = Query(None),
) -> dict[str, Any]:
    with db_read() as conn:
        with conn.cursor() as cur:
            if billing_month:
                month = billing_month
            else:
                cur.execute("SELECT to_char(MAX(charge_date),'YYYY-MM') FROM fact_daily_cost")
                row = cur.fetchone()
                month = row[0] if row and row[0] else "2024-01"

            filters = ["to_char(charge_date,'YYYY-MM') = %s"]
            params: list[Any] = [month]
            if provider:
                filters.append("provider = %s")
                params.append(provider)
            where = "WHERE " + " AND ".join(filters)

            cur.execute(
                f"""
                SELECT env,
                       CAST(SUM(effective_cost) AS DOUBLE PRECISION)  AS cost,
                       COUNT(DISTINCT resource_id)                     AS resource_count,
                       COUNT(DISTINCT team)                            AS team_count
                FROM fact_daily_cost
                {where}
                GROUP BY env
                ORDER BY cost DESC
                """,
                params,
            )
            env_rows = cur.fetchall()

            # cross-tab: env × team
            cur.execute(
                f"""
                SELECT env, team,
                       CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                {where}
                GROUP BY env, team
                ORDER BY env, cost DESC
                """,
                params,
            )
            cross_rows = cur.fetchall()

    grand_total = sum(f(r[1]) for r in env_rows) or 1.0

    envs = [
        {
            "env": r[0],
            "cost": round(f(r[1]), 2),
            "resource_count": int(r[2]),
            "team_count": int(r[3]),
            "pct": round(f(r[1]) / grand_total * 100, 1),
        }
        for r in env_rows
    ]

    cross_map: dict[str, dict[str, float]] = {}
    for env_name, team, cost in cross_rows:
        cross_map.setdefault(env_name, {})[team] = round(f(cost), 2)

    cross_tab = [
        {"env": env_name, "by_team": by_team}
        for env_name, by_team in cross_map.items()
    ]

    return {
        "billing_month": month,
        "grand_total": round(grand_total, 2),
        "envs": envs,
        "cross_tab": cross_tab,
    }
