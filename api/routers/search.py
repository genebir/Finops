"""GET /api/search — global search across resources, teams, and services."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search(
    q: str = Query("", description="Search query"),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Search resources / teams / services by ILIKE match.

    Returns up to 5 results per category (resources, teams, services).
    Empty query returns empty results — never the full table.
    """
    query = (q or "").strip()
    if not query:
        return {
            "query": "",
            "resources": [],
            "teams": [],
            "services": [],
            "total": 0,
        }

    pattern = f"%{query}%"
    per_category = max(1, min(limit // 3 + 1, 10))

    resources: list[dict[str, Any]] = []
    teams: list[dict[str, Any]] = []
    services: list[dict[str, Any]] = []

    with db_read() as conn:
        with conn.cursor() as cur:
            # Resources — match resource_id or resource_name (use inventory if available, else fall back to fact)
            cur.execute(
                "SELECT 1 FROM pg_tables WHERE tablename='dim_resource_inventory' LIMIT 1"
            )
            has_inventory = cur.fetchone() is not None

            if has_inventory:
                cur.execute(
                    """
                    SELECT
                        resource_id,
                        resource_name,
                        service_name,
                        provider,
                        team,
                        env,
                        CAST(total_cost_30d AS DOUBLE PRECISION) AS cost_30d
                    FROM dim_resource_inventory
                    WHERE resource_id ILIKE %s OR resource_name ILIKE %s
                    ORDER BY total_cost_30d DESC
                    LIMIT %s
                    """,
                    (pattern, pattern, per_category),
                )
                resources = [
                    {
                        "resource_id": r[0],
                        "resource_name": r[1],
                        "service_name": r[2],
                        "provider": r[3],
                        "team": r[4],
                        "env": r[5],
                        "cost_30d": round(f(r[6]), 2),
                    }
                    for r in cur.fetchall()
                ]
            else:
                cur.execute(
                    """
                    SELECT
                        resource_id,
                        MAX(resource_name) AS resource_name,
                        MAX(service_name) AS service_name,
                        MAX(provider)     AS provider,
                        MAX(team)         AS team,
                        MAX(env)          AS env,
                        CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost_30d
                    FROM fact_daily_cost
                    WHERE (resource_id ILIKE %s OR resource_name ILIKE %s)
                      AND charge_date >= (
                          SELECT MAX(charge_date) - INTERVAL '30 days' FROM fact_daily_cost
                      )
                    GROUP BY resource_id
                    ORDER BY cost_30d DESC
                    LIMIT %s
                    """,
                    (pattern, pattern, per_category),
                )
                resources = [
                    {
                        "resource_id": r[0],
                        "resource_name": r[1],
                        "service_name": r[2],
                        "provider": r[3],
                        "team": r[4],
                        "env": r[5],
                        "cost_30d": round(f(r[6]), 2),
                    }
                    for r in cur.fetchall()
                ]

            # Teams — match team name (current month cost)
            cur.execute(
                "SELECT to_char(MAX(charge_date),'YYYY-MM') FROM fact_daily_cost"
            )
            row = cur.fetchone()
            latest_month = row[0] if row and row[0] else None

            if latest_month:
                cur.execute(
                    """
                    SELECT
                        team,
                        CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost,
                        COUNT(DISTINCT resource_id) AS resource_count
                    FROM fact_daily_cost
                    WHERE team ILIKE %s
                      AND to_char(charge_date,'YYYY-MM') = %s
                    GROUP BY team
                    ORDER BY cost DESC
                    LIMIT %s
                    """,
                    (pattern, latest_month, per_category),
                )
                teams = [
                    {
                        "team": r[0],
                        "curr_month_cost": round(f(r[1]), 2),
                        "resource_count": int(r[2]),
                    }
                    for r in cur.fetchall()
                ]

                # Services — match service name (current month cost)
                cur.execute(
                    """
                    SELECT
                        service_name,
                        MAX(service_category) AS service_category,
                        CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost,
                        COUNT(DISTINCT resource_id) AS resource_count
                    FROM fact_daily_cost
                    WHERE service_name ILIKE %s
                      AND to_char(charge_date,'YYYY-MM') = %s
                    GROUP BY service_name
                    ORDER BY cost DESC
                    LIMIT %s
                    """,
                    (pattern, latest_month, per_category),
                )
                services = [
                    {
                        "service_name": r[0],
                        "service_category": r[1],
                        "curr_month_cost": round(f(r[2]), 2),
                        "resource_count": int(r[3]),
                    }
                    for r in cur.fetchall()
                ]

    return {
        "query": query,
        "resources": resources,
        "teams": teams,
        "services": services,
        "total": len(resources) + len(teams) + len(services),
    }
