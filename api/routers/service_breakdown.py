"""GET /api/service-breakdown — cost by service category across teams."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/service-breakdown", tags=["service-breakdown"])


@router.get("")
def service_breakdown(
    billing_month: str | None = Query(None, description="YYYY-MM"),
    team: str | None = Query(None),
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
            if team:
                filters.append("team = %s")
                params.append(team)
            if provider:
                filters.append("provider = %s")
                params.append(provider)
            where = "WHERE " + " AND ".join(filters)

            # by service_category
            cur.execute(
                f"""
                SELECT
                    COALESCE(service_category, 'other')   AS category,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost,
                    COUNT(DISTINCT resource_id)           AS resource_count
                FROM fact_daily_cost
                {where}
                GROUP BY category
                ORDER BY cost DESC
                """,
                params,
            )
            cat_rows = cur.fetchall()

            # by service_name (top 15)
            cur.execute(
                f"""
                SELECT
                    COALESCE(service_name, 'unknown')     AS service_name,
                    COALESCE(service_category, 'other')   AS category,
                    CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost,
                    COUNT(DISTINCT resource_id)           AS resource_count
                FROM fact_daily_cost
                {where}
                GROUP BY service_name, category
                ORDER BY cost DESC
                LIMIT 15
                """,
                params,
            )
            svc_rows = cur.fetchall()

    grand_total = sum(f(r[1]) for r in cat_rows) or 1.0

    by_category = [
        {
            "category": r[0],
            "cost": round(f(r[1]), 2),
            "resource_count": int(r[2]),
            "pct": round(f(r[1]) / grand_total * 100, 1),
        }
        for r in cat_rows
    ]

    by_service = [
        {
            "service_name": r[0],
            "category": r[1],
            "cost": round(f(r[2]), 2),
            "resource_count": int(r[3]),
            "pct": round(f(r[2]) / grand_total * 100, 1),
        }
        for r in svc_rows
    ]

    return {
        "billing_month": month,
        "grand_total": round(grand_total, 2),
        "by_category": by_category,
        "by_service": by_service,
    }
