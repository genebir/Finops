"""Burn rate endpoint — MTD spend velocity and projected end-of-month cost."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read

router = APIRouter(prefix="/api", tags=["burn-rate"])


@router.get("/burn-rate")
def get_burn_rate(billing_month: str | None = Query(default=None)) -> dict[str, Any]:
    """Return burn rate rows for the requested month (defaults to current month)."""
    import datetime
    month = billing_month or datetime.date.today().strftime("%Y-%m")

    with db_read() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_burn_rate'"
            )
            if cur.fetchone() is None:
                return {"billing_month": month, "items": [], "summary": {}}

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT team, env, days_elapsed, days_in_month,
                       mtd_cost, daily_avg, projected_eom,
                       budget_amount, projected_utilization, status,
                       refreshed_at
                FROM dim_burn_rate
                WHERE billing_month = %s
                ORDER BY projected_eom DESC
                """,
                (month,),
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()

    items = []
    for row in rows:
        r = dict(zip(cols, row))
        if r.get("refreshed_at"):
            r["refreshed_at"] = r["refreshed_at"].isoformat()
        items.append(r)

    total_mtd = sum(r["mtd_cost"] for r in items)
    total_projected = sum(r["projected_eom"] for r in items)
    critical_count = sum(1 for r in items if r["status"] == "critical")

    return {
        "billing_month": month,
        "items": items,
        "summary": {
            "total_mtd": round(total_mtd, 2),
            "total_projected_eom": round(total_projected, 2),
            "critical_count": critical_count,
            "warning_count": sum(1 for r in items if r["status"] == "warning"),
            "on_track_count": sum(1 for r in items if r["status"] == "on_track"),
        },
    }
