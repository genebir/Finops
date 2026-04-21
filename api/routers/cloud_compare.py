"""GET /api/cloud-compare — side-by-side multi-cloud cost breakdown."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/cloud-compare", tags=["cloud-compare"])


@router.get("")
def cloud_compare(
    billing_month: str | None = Query(None, description="YYYY-MM, default = latest"),
    team: str | None = Query(None),
) -> dict[str, Any]:
    with db_read() as conn:
        with conn.cursor() as cur:
            # resolve month
            if billing_month:
                month = billing_month
            else:
                cur.execute("SELECT to_char(MAX(charge_date), 'YYYY-MM') FROM fact_daily_cost")
                row = cur.fetchone()
                month = row[0] if row and row[0] else "2024-01"

            team_filter = "AND team = %s" if team else ""
            base_params: list[Any] = [month]
            if team:
                base_params.append(team)

            # total per provider
            cur.execute(
                f"""
                SELECT provider,
                       CAST(SUM(effective_cost) AS DOUBLE PRECISION)   AS total_cost,
                       COUNT(DISTINCT resource_id)                      AS resource_count
                FROM fact_daily_cost
                WHERE to_char(charge_date, 'YYYY-MM') = %s {team_filter}
                GROUP BY provider
                ORDER BY total_cost DESC
                """,
                base_params,
            )
            provider_rows = cur.fetchall()

            grand_total = sum(f(r[1]) for r in provider_rows) or 1.0

            providers = [
                {
                    "provider": r[0],
                    "total_cost": round(f(r[1]), 2),
                    "resource_count": int(r[2]),
                    "pct": round(f(r[1]) / grand_total * 100, 1),
                }
                for r in provider_rows
            ]

            # top services per provider
            cur.execute(
                f"""
                SELECT provider,
                       COALESCE(service_name, 'unknown')               AS svc,
                       CAST(SUM(effective_cost) AS DOUBLE PRECISION)   AS cost
                FROM fact_daily_cost
                WHERE to_char(charge_date, 'YYYY-MM') = %s {team_filter}
                GROUP BY provider, svc
                ORDER BY provider, cost DESC
                """,
                base_params,
            )
            svc_rows = cur.fetchall()

            svc_by_provider: dict[str, list[dict[str, Any]]] = {}
            for prov, svc, cost in svc_rows:
                svc_by_provider.setdefault(prov, []).append(
                    {"service": svc, "cost": round(f(cost), 2)}
                )
            for prov in svc_by_provider:
                svc_by_provider[prov] = svc_by_provider[prov][:5]

            # monthly trend per provider (last 6 months)
            cur.execute(
                f"""
                SELECT provider,
                       to_char(charge_date, 'YYYY-MM')                 AS billing_month,
                       CAST(SUM(effective_cost) AS DOUBLE PRECISION)   AS cost
                FROM fact_daily_cost
                WHERE charge_date >= (
                    SELECT MAX(charge_date) - INTERVAL '180 days' FROM fact_daily_cost
                )
                {team_filter.replace('AND team = %s', f"AND team = '{team}'" if team else "")}
                GROUP BY provider, billing_month
                ORDER BY provider, billing_month
                """,
                [p for p in base_params if p != month],
            )
            trend_rows = cur.fetchall()

            trend_by_provider: dict[str, list[dict[str, Any]]] = {}
            for prov, bm, cost in trend_rows:
                trend_by_provider.setdefault(prov, []).append(
                    {"month": bm, "cost": round(f(cost), 2)}
                )

            # team breakdown across providers
            cur.execute(
                f"""
                SELECT team, provider,
                       CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                WHERE to_char(charge_date, 'YYYY-MM') = %s {team_filter}
                GROUP BY team, provider
                ORDER BY team, cost DESC
                """,
                base_params,
            )
            team_rows = cur.fetchall()

            teams_map: dict[str, dict[str, float]] = {}
            for t, prov, cost in team_rows:
                teams_map.setdefault(t, {})[prov] = round(f(cost), 2)

            teams = [
                {"team": t, "by_provider": costs, "total": round(sum(costs.values()), 2)}
                for t, costs in teams_map.items()
            ]
            teams.sort(key=lambda x: -x["total"])

    return {
        "billing_month": month,
        "grand_total": round(grand_total, 2),
        "providers": providers,
        "top_services_by_provider": svc_by_provider,
        "trend_by_provider": trend_by_provider,
        "teams": teams,
    }
