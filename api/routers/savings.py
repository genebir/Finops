"""GET /api/savings — realized savings from cost recommendations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/savings", tags=["savings"])


@router.get("")
def get_savings(
    billing_month: str | None = Query(None, description="YYYY-MM"),
    team: str | None = Query(None),
    status: str | None = Query(None, description="realized|partial|pending|cost_increased"),
) -> dict[str, Any]:
    with db_read() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_savings_realized'"
            )
            if not cur.fetchone():
                return {
                    "billing_month": billing_month or "N/A",
                    "items": [],
                    "summary": {"total_estimated": 0, "total_realized": 0, "realized_count": 0, "partial_count": 0, "pending_count": 0},
                }

            if billing_month:
                month = billing_month
            else:
                cur.execute("SELECT MAX(billing_month) FROM dim_savings_realized")
                row = cur.fetchone()
                month = row[0] if row and row[0] else "N/A"

            filters: list[str] = ["billing_month = %s"]
            params: list[Any] = [month]
            if team:
                filters.append("team = %s")
                params.append(team)
            if status:
                filters.append("status = %s")
                params.append(status)
            where = "WHERE " + " AND ".join(filters)

            cur.execute(
                f"""
                SELECT resource_id, team, product, env, provider,
                       recommendation_type, estimated_savings,
                       realized_savings, prev_month_cost, curr_month_cost, status
                FROM dim_savings_realized
                {where}
                ORDER BY estimated_savings DESC
                """,
                params,
            )
            rows = cur.fetchall()

            cur.execute(
                f"""
                SELECT
                    CAST(SUM(estimated_savings) AS DOUBLE PRECISION),
                    CAST(SUM(COALESCE(realized_savings, 0)) AS DOUBLE PRECISION),
                    COUNT(*) FILTER (WHERE status = 'realized'),
                    COUNT(*) FILTER (WHERE status = 'partial'),
                    COUNT(*) FILTER (WHERE status = 'pending'),
                    COUNT(*) FILTER (WHERE status = 'cost_increased')
                FROM dim_savings_realized
                {where}
                """,
                params,
            )
            s = cur.fetchone()

    items = [
        {
            "resource_id": r[0], "team": r[1], "product": r[2], "env": r[3],
            "provider": r[4], "recommendation_type": r[5],
            "estimated_savings": round(f(r[6]), 2),
            "realized_savings": round(f(r[7]), 2) if r[7] is not None else None,
            "prev_month_cost": round(f(r[8]), 2) if r[8] is not None else None,
            "curr_month_cost": round(f(r[9]), 2) if r[9] is not None else None,
            "status": r[10],
        }
        for r in rows
    ]

    summary: dict[str, Any] = {
        "total_estimated": round(f(s[0]), 2) if s and s[0] else 0.0,
        "total_realized": round(f(s[1]), 2) if s and s[1] else 0.0,
        "realized_count": int(s[2]) if s else 0,
        "partial_count": int(s[3]) if s else 0,
        "pending_count": int(s[4]) if s else 0,
        "cost_increased_count": int(s[5]) if s else 0,
    }

    return {"billing_month": month, "items": items, "summary": summary}
