"""GET /api/leaderboard — team cost ranking with MoM change."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("")
def leaderboard(
    billing_month: str | None = Query(None, description="YYYY-MM"),
    provider: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    with db_read() as conn:
        with conn.cursor() as cur:
            # resolve current and previous months
            if billing_month:
                curr_month = billing_month
            else:
                cur.execute("SELECT to_char(MAX(charge_date),'YYYY-MM') FROM fact_daily_cost")
                row = cur.fetchone()
                curr_month = row[0] if row and row[0] else "2024-01"

            # compute previous month
            try:
                import datetime
                dt = datetime.date.fromisoformat(curr_month + "-01")
                prev_dt = (dt - datetime.timedelta(days=1)).replace(day=1)
                prev_month = prev_dt.strftime("%Y-%m")
            except ValueError:
                prev_month = curr_month

            prov_filter = "AND provider = %s" if provider else ""
            base_params: list[Any] = [curr_month, prev_month]
            if provider:
                base_params.append(provider)

            cur.execute(
                f"""
                SELECT
                    team,
                    CAST(SUM(CASE WHEN to_char(charge_date,'YYYY-MM') = %s
                                  THEN effective_cost ELSE 0 END) AS DOUBLE PRECISION) AS curr_cost,
                    CAST(SUM(CASE WHEN to_char(charge_date,'YYYY-MM') = %s
                                  THEN effective_cost ELSE 0 END) AS DOUBLE PRECISION) AS prev_cost,
                    COUNT(DISTINCT resource_id) AS resource_count
                FROM fact_daily_cost
                WHERE to_char(charge_date,'YYYY-MM') IN (%s, %s)
                {prov_filter}
                GROUP BY team
                ORDER BY curr_cost DESC
                LIMIT %s
                """,
                [curr_month, prev_month, curr_month, prev_month] + ([provider] if provider else []) + [limit],
            )
            rows = cur.fetchall()

    total_curr = sum(f(r[1]) for r in rows) or 1.0

    items = []
    for rank, row in enumerate(rows, 1):
        team, curr_cost, prev_cost, resource_count = row
        curr = f(curr_cost)
        prev = f(prev_cost)
        mom_change_pct = ((curr - prev) / prev * 100) if prev > 0 else None
        items.append({
            "rank": rank,
            "team": team,
            "curr_cost": round(curr, 2),
            "prev_cost": round(prev, 2),
            "mom_change_pct": round(mom_change_pct, 1) if mom_change_pct is not None else None,
            "pct_of_total": round(curr / total_curr * 100, 1),
            "resource_count": int(resource_count),
        })

    return {
        "billing_month": curr_month,
        "prev_month": prev_month,
        "items": items,
        "summary": {
            "total_curr": round(total_curr, 2),
            "total_prev": round(sum(f(r[2]) for r in rows), 2),
            "team_count": len(items),
        },
    }
