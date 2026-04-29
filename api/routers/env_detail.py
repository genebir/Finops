"""GET /api/environments/{env} — environment detail: cost history, team breakdown, resources."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/environments", tags=["env-detail"])


@router.get("/{env}")
def env_detail(
    env: str,
    months: int = Query(6, ge=1, le=24),
) -> dict[str, Any]:
    """Returns environment-level aggregates: monthly cost, team/service breakdown, top resources."""
    with db_read() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM fact_daily_cost WHERE env = %s",
                (env,),
            )
            row = cur.fetchone()
            if not row or (row[0] == 0):
                raise HTTPException(status_code=404, detail=f"Environment '{env}' not found")

            cur.execute(
                "SELECT to_char(MAX(charge_date),'YYYY-MM') FROM fact_daily_cost WHERE env = %s",
                (env,),
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
                WHERE env = %s
                GROUP BY billing_month
                ORDER BY billing_month DESC
                LIMIT %s
                """,
                (env, months),
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

            # By team (latest month)
            cur.execute(
                """
                SELECT
                    team,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost,
                    COUNT(DISTINCT resource_id) AS resource_count
                FROM fact_daily_cost
                WHERE env = %s AND to_char(charge_date,'YYYY-MM') = %s
                GROUP BY team
                ORDER BY cost DESC
                """,
                (env, latest_month),
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
                WHERE env = %s AND to_char(charge_date,'YYYY-MM') = %s
                GROUP BY provider
                ORDER BY cost DESC
                """,
                (env, latest_month),
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

            # By service (latest month, top 10)
            cur.execute(
                """
                SELECT
                    service_name,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                WHERE env = %s AND to_char(charge_date,'YYYY-MM') = %s
                GROUP BY service_name
                ORDER BY cost DESC
                LIMIT 10
                """,
                (env, latest_month),
            )
            svc_rows = cur.fetchall()
            svc_total = sum(f(r[1]) for r in svc_rows) or 1.0
            by_service = [
                {
                    "service_name": r[0],
                    "cost": round(f(r[1]), 2),
                    "pct": round(f(r[1]) / svc_total * 100, 1),
                }
                for r in svc_rows
            ]

            # Top resources (latest month)
            cur.execute(
                """
                SELECT
                    resource_id,
                    MAX(resource_name) AS resource_name,
                    MAX(team) AS team,
                    MAX(service_name) AS service_name,
                    MAX(provider) AS provider,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                WHERE env = %s AND to_char(charge_date,'YYYY-MM') = %s
                GROUP BY resource_id
                ORDER BY cost DESC
                LIMIT 10
                """,
                (env, latest_month),
            )
            resource_rows = cur.fetchall()
            top_resources = [
                {
                    "resource_id": r[0],
                    "resource_name": r[1],
                    "team": r[2],
                    "service_name": r[3],
                    "provider": r[4],
                    "cost": round(f(r[5]), 2),
                }
                for r in resource_rows
            ]

            # Summary
            curr_cost = monthly_trend[-1]["total_cost"] if monthly_trend else 0.0
            prev_cost = monthly_trend[-2]["total_cost"] if len(monthly_trend) >= 2 else 0.0
            mom_change_pct = (
                round((curr_cost - prev_cost) / prev_cost * 100, 1) if prev_cost > 0 else None
            )

            cur.execute(
                """
                SELECT COUNT(DISTINCT resource_id)
                FROM fact_daily_cost
                WHERE env = %s AND to_char(charge_date,'YYYY-MM') = %s
                """,
                (env, latest_month),
            )
            row = cur.fetchone()
            resource_count = int(row[0]) if row else 0

    return {
        "env": env,
        "latest_month": latest_month,
        "monthly_trend": monthly_trend,
        "by_team": by_team,
        "by_provider": by_provider,
        "by_service": by_service,
        "top_resources": top_resources,
        "summary": {
            "curr_cost": round(curr_cost, 2),
            "prev_cost": round(prev_cost, 2),
            "mom_change_pct": mom_change_pct,
            "resource_count": resource_count,
            "team_count": len(by_team),
        },
    }
