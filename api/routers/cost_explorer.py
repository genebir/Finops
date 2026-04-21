"""GET /api/cost-explorer — daily + service + provider breakdowns."""

from fastapi import APIRouter, Query

from ..deps import columns, db_read, f, tables
from ..models import (
    CostExplorerResponse,
    DailyCost,
    ProviderCost,
    ServiceCost,
)

router = APIRouter(tags=["cost-explorer"])


@router.get("/api/cost-explorer", response_model=CostExplorerResponse)
def get_cost_explorer(
    team: str | None = Query(None),
    env: str | None = Query(None),
    service: str | None = Query(None),
    provider: str | None = Query(None, description="aws | gcp | azure"),
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None, description="YYYY-MM-DD"),
) -> CostExplorerResponse:
    with db_read() as db:
        cur = db.cursor()
        has_provider_col = (
            "fact_daily_cost" in tables(db)
            and "provider" in columns(db, "fact_daily_cost")
        )

        conditions: list[str] = []
        params: list[object] = []
        if team:
            conditions.append("team = %s")
            params.append(team)
        if env:
            conditions.append("env = %s")
            params.append(env)
        if service:
            conditions.append("service_name = %s")
            params.append(service)
        if provider and has_provider_col:
            conditions.append("provider = %s")
            params.append(provider)
        if start:
            conditions.append("charge_date >= %s::DATE")
            params.append(start)
        if end:
            conditions.append("charge_date <= %s::DATE")
            params.append(end)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(
            f"""
            SELECT charge_date::TEXT, CAST(SUM(effective_cost) AS DOUBLE PRECISION)
            FROM fact_daily_cost {where}
            GROUP BY charge_date ORDER BY charge_date
            """,
            params,
        )
        daily_rows = cur.fetchall()

        cur.execute(
            f"""
            SELECT service_name, CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
            FROM fact_daily_cost {where}
            GROUP BY service_name ORDER BY cost DESC
            LIMIT 20
            """,
            params,
        )
        service_rows = cur.fetchall()

        provider_rows: list[tuple[str, float]] = []
        if has_provider_col:
            cur.execute(
                f"""
                SELECT provider, CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost {where}
                GROUP BY provider ORDER BY cost DESC
                """,
                params,
            )
            provider_rows = [(r[0], f(r[1])) for r in cur.fetchall()]

        cur.close()

        total = sum(f(r[1]) for r in daily_rows) or 1.0
        avg_daily = total / len(daily_rows) if daily_rows else 0.0

        return CostExplorerResponse(
            daily=[DailyCost(charge_date=r[0], cost=f(r[1])) for r in daily_rows],
            by_service=[
                ServiceCost(
                    service_name=r[0] or "Unknown",
                    cost=f(r[1]),
                    pct=round(f(r[1]) / total * 100, 1),
                )
                for r in service_rows
            ],
            by_provider=[
                ProviderCost(
                    provider=p or "unknown",
                    cost=c,
                    pct=round(c / total * 100, 1),
                )
                for p, c in provider_rows
            ],
            total=round(total, 2),
            avg_daily=round(avg_daily, 2),
        )
