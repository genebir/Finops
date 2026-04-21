"""GET /api/chargeback — per-team cost allocation with month selection."""

from fastapi import APIRouter, Query

from ..deps import db_read, f, tables
from ..models import ChargebackItem, ChargebackResponse, ChargebackTeam

router = APIRouter(tags=["chargeback"])


@router.get("/api/chargeback", response_model=ChargebackResponse)
def get_chargeback(
    billing_month: str | None = Query(
        None, description="YYYY-MM (falls back to latest month if omitted)"
    ),
) -> ChargebackResponse:
    with db_read() as db:
        cur = db.cursor()
        _tables = tables(db)

        available_months: list[str] = []
        if "fact_daily_cost" in _tables:
            cur.execute(
                "SELECT DISTINCT to_char(charge_date, 'YYYY-MM') AS m "
                "FROM fact_daily_cost ORDER BY m DESC"
            )
            available_months = [r[0] for r in cur.fetchall() if r[0]]

        if "dim_chargeback" in _tables:
            if not billing_month:
                cur.execute(
                    "SELECT MAX(billing_month)::TEXT FROM dim_chargeback"
                )
                month_row = cur.fetchone()
                billing_month = month_row[0] if month_row and month_row[0] else None
            month_label = billing_month or "unknown"
            cur.execute(
                """
                SELECT team, product, env, CAST(SUM(actual_cost) AS DOUBLE PRECISION) AS cost
                FROM dim_chargeback
                WHERE billing_month = %s
                GROUP BY team, product, env ORDER BY cost DESC
                """,
                [month_label],
            )
            rows = cur.fetchall()
        else:
            month_label = billing_month or (available_months[0] if available_months else "unknown")
            cur.execute(
                """
                SELECT team, product, env, CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                WHERE to_char(charge_date, 'YYYY-MM') = %s
                GROUP BY team, product, env ORDER BY cost DESC
                """,
                [month_label],
            )
            rows = cur.fetchall()

        cur.close()

        total = sum(f(r[3]) for r in rows) or 1.0

        items = [
            ChargebackItem(
                team=r[0], product=r[1], env=r[2],
                cost=f(r[3]), pct=round(f(r[3]) / total * 100, 1),
            )
            for r in rows
        ]

        team_totals: dict[str, dict[str, float]] = {}
        for item in items:
            bucket = team_totals.setdefault(item.team, {"cost": 0.0, "count": 0.0})
            bucket["cost"] += item.cost
            bucket["count"] += 1

        by_team = [
            ChargebackTeam(
                team=t,
                cost=round(v["cost"], 2),
                pct=round(v["cost"] / total * 100, 1),
                resource_count=int(v["count"]),
            )
            for t, v in sorted(team_totals.items(), key=lambda x: -x[1]["cost"])
        ]

        return ChargebackResponse(
            billing_month=month_label,
            available_months=available_months,
            total_cost=round(total, 2),
            by_team=by_team,
            items=items,
        )
