"""GET /api/teams/{team} — team detail: cost history, service breakdown, anomalies, resources."""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/teams", tags=["team-detail"])


@router.get("/{team}")
def team_detail(
    team: str,
    months: int = Query(6, ge=1, le=24),
) -> dict[str, Any]:
    """Returns team-level aggregates: monthly cost, service breakdown, top resources, anomalies."""
    with db_read() as conn:
        with conn.cursor() as cur:
            # Verify team exists
            cur.execute(
                "SELECT COUNT(DISTINCT team) FROM fact_daily_cost WHERE team = %s",
                (team,),
            )
            row = cur.fetchone()
            if not row or (row[0] == 0):
                raise HTTPException(status_code=404, detail=f"Team '{team}' not found")

            # Latest month
            cur.execute(
                "SELECT to_char(MAX(charge_date),'YYYY-MM') FROM fact_daily_cost WHERE team = %s",
                (team,),
            )
            row = cur.fetchone()
            latest_month = row[0] if row and row[0] else "2024-01"

            # Monthly cost trend (last N months)
            cur.execute(
                """
                SELECT
                    to_char(charge_date,'YYYY-MM') AS billing_month,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS total_cost,
                    COUNT(DISTINCT resource_id) AS resource_count
                FROM fact_daily_cost
                WHERE team = %s
                GROUP BY billing_month
                ORDER BY billing_month DESC
                LIMIT %s
                """,
                (team, months),
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

            # Service breakdown (latest month)
            cur.execute(
                """
                SELECT
                    service_name,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost,
                    COUNT(DISTINCT resource_id) AS resource_count
                FROM fact_daily_cost
                WHERE team = %s AND to_char(charge_date,'YYYY-MM') = %s
                GROUP BY service_name
                ORDER BY cost DESC
                LIMIT 10
                """,
                (team, latest_month),
            )
            svc_rows = cur.fetchall()
            svc_total = sum(f(r[1]) for r in svc_rows) or 1.0
            by_service = [
                {
                    "service_name": r[0],
                    "cost": round(f(r[1]), 2),
                    "resource_count": int(r[2]),
                    "pct": round(f(r[1]) / svc_total * 100, 1),
                }
                for r in svc_rows
            ]

            # Environment breakdown (latest month)
            cur.execute(
                """
                SELECT
                    env,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                WHERE team = %s AND to_char(charge_date,'YYYY-MM') = %s
                GROUP BY env
                ORDER BY cost DESC
                """,
                (team, latest_month),
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

            # Provider breakdown (latest month)
            cur.execute(
                """
                SELECT
                    provider,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                WHERE team = %s AND to_char(charge_date,'YYYY-MM') = %s
                GROUP BY provider
                ORDER BY cost DESC
                """,
                (team, latest_month),
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

            # Top resources (latest month)
            cur.execute(
                """
                SELECT
                    resource_id,
                    MAX(resource_name) AS resource_name,
                    MAX(service_name) AS service_name,
                    MAX(env) AS env,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                WHERE team = %s AND to_char(charge_date,'YYYY-MM') = %s
                GROUP BY resource_id
                ORDER BY cost DESC
                LIMIT 10
                """,
                (team, latest_month),
            )
            resource_rows = cur.fetchall()
            top_resources = [
                {
                    "resource_id": r[0],
                    "resource_name": r[1],
                    "service_name": r[2],
                    "env": r[3],
                    "cost": round(f(r[4]), 2),
                }
                for r in resource_rows
            ]

            # Recent anomalies
            anomalies: list[dict[str, Any]] = []
            try:
                cur.execute("SELECT 1 FROM pg_tables WHERE tablename='anomaly_scores' LIMIT 1")
                if cur.fetchone():
                    cur.execute(
                        """
                        SELECT resource_id, charge_date::TEXT, severity, detector_name,
                               CAST(effective_cost AS DOUBLE PRECISION) AS eff,
                               CAST(z_score AS DOUBLE PRECISION) AS z
                        FROM anomaly_scores
                        WHERE team = %s
                        ORDER BY charge_date DESC
                        LIMIT 10
                        """,
                        (team,),
                    )
                    anomalies = [
                        {
                            "resource_id": r[0],
                            "charge_date": r[1],
                            "severity": r[2],
                            "detector_name": r[3],
                            "effective_cost": round(f(r[4]), 2),
                            "z_score": round(f(r[5]), 2),
                        }
                        for r in cur.fetchall()
                    ]
            except Exception:
                pass

            # Summary
            curr_cost = monthly_trend[-1]["total_cost"] if monthly_trend else 0.0
            prev_cost = monthly_trend[-2]["total_cost"] if len(monthly_trend) >= 2 else 0.0
            mom_change_pct = (
                round((curr_cost - prev_cost) / prev_cost * 100, 1) if prev_cost > 0 else None
            )

    return {
        "team": team,
        "latest_month": latest_month,
        "monthly_trend": monthly_trend,
        "by_service": by_service,
        "by_env": by_env,
        "by_provider": by_provider,
        "top_resources": top_resources,
        "anomalies": anomalies,
        "summary": {
            "curr_cost": round(curr_cost, 2),
            "prev_cost": round(prev_cost, 2),
            "mom_change_pct": mom_change_pct,
            "resource_count": top_resources.__len__() if top_resources else 0,
            "anomaly_count": len(anomalies),
        },
    }
