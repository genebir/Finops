"""GET /api/services/{service_name} — service detail: cost history, team breakdown, resources."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/services", tags=["service-detail"])


@router.get("/{service_name}")
def service_detail(
    service_name: str,
    months: int = Query(6, ge=1, le=24),
) -> dict[str, Any]:
    """Returns service-level aggregates: monthly cost, team breakdown, top resources."""
    with db_read() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT service_name) FROM fact_daily_cost WHERE service_name = %s",
                (service_name,),
            )
            row = cur.fetchone()
            if not row or (row[0] == 0):
                raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")

            cur.execute(
                "SELECT to_char(MAX(charge_date),'YYYY-MM') FROM fact_daily_cost WHERE service_name = %s",
                (service_name,),
            )
            row = cur.fetchone()
            latest_month = row[0] if row and row[0] else "2024-01"

            # Monthly cost trend
            cur.execute(
                """
                SELECT
                    to_char(charge_date,'YYYY-MM') AS billing_month,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS total_cost,
                    COUNT(DISTINCT resource_id) AS resource_count
                FROM fact_daily_cost
                WHERE service_name = %s
                GROUP BY billing_month
                ORDER BY billing_month DESC
                LIMIT %s
                """,
                (service_name, months),
            )
            monthly_rows = cur.fetchall()
            monthly_trend = [
                {
                    "billing_month": r[0],
                    "total_cost": round(f(r[1]), 2),
                    "resource_count": int(r[2]),
                }
                for r in reversed(monthly_rows)
            ]

            # By team (latest month, top 10)
            cur.execute(
                """
                SELECT
                    team,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost,
                    COUNT(DISTINCT resource_id) AS resource_count
                FROM fact_daily_cost
                WHERE service_name = %s AND to_char(charge_date,'YYYY-MM') = %s
                GROUP BY team
                ORDER BY cost DESC
                LIMIT 10
                """,
                (service_name, latest_month),
            )
            team_rows = cur.fetchall()
            team_total = sum(f(r[1]) for r in team_rows) or 1.0
            by_team = [
                {
                    "team": r[0],
                    "cost": round(f(r[1]), 2),
                    "resource_count": int(r[2]),
                    "pct": round(f(r[1]) / team_total * 100, 1),
                }
                for r in team_rows
            ]

            # By provider
            cur.execute(
                """
                SELECT
                    provider,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                WHERE service_name = %s AND to_char(charge_date,'YYYY-MM') = %s
                GROUP BY provider
                ORDER BY cost DESC
                """,
                (service_name, latest_month),
            )
            prov_rows = cur.fetchall()
            prov_total = sum(f(r[1]) for r in prov_rows) or 1.0
            by_provider = [
                {
                    "provider": r[0],
                    "cost": round(f(r[1]), 2),
                    "pct": round(f(r[1]) / prov_total * 100, 1),
                }
                for r in prov_rows
            ]

            # By env
            cur.execute(
                """
                SELECT
                    env,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                WHERE service_name = %s AND to_char(charge_date,'YYYY-MM') = %s
                GROUP BY env
                ORDER BY cost DESC
                """,
                (service_name, latest_month),
            )
            env_rows = cur.fetchall()
            env_total = sum(f(r[1]) for r in env_rows) or 1.0
            by_env = [
                {
                    "env": r[0],
                    "cost": round(f(r[1]), 2),
                    "pct": round(f(r[1]) / env_total * 100, 1),
                }
                for r in env_rows
            ]

            # Top resources (latest month)
            cur.execute(
                """
                SELECT
                    resource_id,
                    MAX(resource_name) AS resource_name,
                    MAX(team) AS team,
                    MAX(env) AS env,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                WHERE service_name = %s AND to_char(charge_date,'YYYY-MM') = %s
                GROUP BY resource_id
                ORDER BY cost DESC
                LIMIT 10
                """,
                (service_name, latest_month),
            )
            resource_rows = cur.fetchall()
            top_resources = [
                {
                    "resource_id": r[0],
                    "resource_name": r[1],
                    "team": r[2],
                    "env": r[3],
                    "cost": round(f(r[4]), 2),
                }
                for r in resource_rows
            ]

            # Summary
            curr_cost = monthly_trend[-1]["total_cost"] if monthly_trend else 0.0
            prev_cost = monthly_trend[-2]["total_cost"] if len(monthly_trend) >= 2 else 0.0
            mom_change_pct = (
                round((curr_cost - prev_cost) / prev_cost * 100, 1) if prev_cost > 0 else None
            )

            team_count = len(by_team)

    return {
        "service_name": service_name,
        "latest_month": latest_month,
        "monthly_trend": monthly_trend,
        "by_team": by_team,
        "by_provider": by_provider,
        "by_env": by_env,
        "top_resources": top_resources,
        "summary": {
            "curr_cost": round(curr_cost, 2),
            "prev_cost": round(prev_cost, 2),
            "mom_change_pct": mom_change_pct,
            "resource_count": len(top_resources),
            "team_count": team_count,
        },
    }
