"""GET /api/budget-forecast — EOM projections per (team, env)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/budget-forecast", tags=["budget-forecast"])


@router.get("")
def budget_forecast_endpoint(
    billing_month: str | None = Query(None),
    team: str | None = Query(None),
    risk_level: str | None = Query(None, description="normal|warning|over"),
) -> dict[str, Any]:
    with db_read() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_budget_forecast'"
            )
            if not cur.fetchone():
                return {"billing_month": billing_month or "N/A", "items": [], "summary": {}}

            if billing_month:
                month = billing_month
            else:
                cur.execute("SELECT MAX(billing_month) FROM dim_budget_forecast")
                row = cur.fetchone()
                month = row[0] if row and row[0] else "N/A"

            filters = ["billing_month = %s"]
            params: list[Any] = [month]
            if team:
                filters.append("team = %s")
                params.append(team)
            if risk_level:
                filters.append("risk_level = %s")
                params.append(risk_level)
            where = "WHERE " + " AND ".join(filters)

            cur.execute(
                f"""
                SELECT team, env, days_elapsed, days_in_month,
                       mtd_cost, projected_eom, lower_bound, upper_bound,
                       budget_amount, projected_pct, risk_level
                FROM dim_budget_forecast
                {where}
                ORDER BY projected_eom DESC
                """,
                params,
            )
            rows = cur.fetchall()

            cur.execute(
                f"""
                SELECT
                    CAST(SUM(projected_eom) AS DOUBLE PRECISION),
                    COUNT(*) FILTER (WHERE risk_level = 'over'),
                    COUNT(*) FILTER (WHERE risk_level = 'warning'),
                    COUNT(*) FILTER (WHERE risk_level = 'normal')
                FROM dim_budget_forecast
                {where}
                """,
                params,
            )
            s = cur.fetchone()

    items = [
        {
            "team": r[0], "env": r[1],
            "days_elapsed": int(r[2]), "days_in_month": int(r[3]),
            "mtd_cost": round(f(r[4]), 2),
            "projected_eom": round(f(r[5]), 2),
            "lower_bound": round(f(r[6]), 2),
            "upper_bound": round(f(r[7]), 2),
            "budget_amount": round(f(r[8]), 2) if r[8] is not None else None,
            "projected_pct": round(f(r[9]), 1) if r[9] is not None else None,
            "risk_level": r[10],
        }
        for r in rows
    ]

    summary: dict[str, Any] = {
        "total_projected_eom": round(f(s[0]), 2) if s and s[0] else 0.0,
        "over_budget_count": int(s[1]) if s else 0,
        "warning_count": int(s[2]) if s else 0,
        "normal_count": int(s[3]) if s else 0,
    }

    return {"billing_month": month, "items": items, "summary": summary}
