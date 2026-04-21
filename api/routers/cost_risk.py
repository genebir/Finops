"""GET /api/cost-risk — high-cost resources with elevated anomaly frequency (cost-risk correlation)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read, f, tables

router = APIRouter(prefix="/api/cost-risk", tags=["cost-risk"])


@router.get("")
def cost_risk(
    billing_month: str | None = Query(None, description="YYYY-MM"),
    provider: str | None = Query(None),
    team: str | None = Query(None),
    min_anomaly_count: int = Query(1, ge=0, description="Min anomaly count to include"),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    """Returns resources ranked by risk score = normalized_cost × normalized_anomaly_count."""
    with db_read() as conn:
        with conn.cursor() as cur:
            if billing_month:
                month = billing_month
            else:
                cur.execute("SELECT to_char(MAX(charge_date),'YYYY-MM') FROM fact_daily_cost")
                row = cur.fetchone()
                month = row[0] if row and row[0] else "2024-01"

            has_anomaly = "anomaly_scores" in tables(conn)

            cost_filters = ["to_char(f.charge_date, 'YYYY-MM') = %s"]
            params: list[Any] = [month]
            if provider:
                cost_filters.append("f.provider = %s")
                params.append(provider)
            if team:
                cost_filters.append("f.team = %s")
                params.append(team)
            cost_where = "WHERE " + " AND ".join(cost_filters)

            if has_anomaly:
                cur.execute(
                    f"""
                    SELECT
                        f.resource_id,
                        f.team,
                        f.env,
                        f.provider,
                        COALESCE(f.service_name, 'unknown')            AS service_name,
                        CAST(SUM(f.effective_cost) AS DOUBLE PRECISION) AS total_cost,
                        COUNT(DISTINCT a.charge_date)                   AS anomaly_count,
                        CAST(SUM(f.effective_cost) AS DOUBLE PRECISION) /
                            NULLIF(MAX(SUM(f.effective_cost)) OVER (), 0) *
                            (COUNT(DISTINCT a.charge_date)::DOUBLE PRECISION /
                             NULLIF(MAX(COUNT(DISTINCT a.charge_date)) OVER (), 0))
                            AS risk_score
                    FROM fact_daily_cost f
                    LEFT JOIN anomaly_scores a
                        ON a.resource_id = f.resource_id
                        AND to_char(a.charge_date, 'YYYY-MM') = %s
                        AND a.is_anomaly = TRUE
                    {cost_where}
                    GROUP BY f.resource_id, f.team, f.env, f.provider, service_name
                    HAVING COUNT(DISTINCT a.charge_date) >= %s
                    ORDER BY risk_score DESC NULLS LAST
                    LIMIT %s
                    """,
                    [month] + params + [min_anomaly_count, limit],
                )
            else:
                cur.execute(
                    f"""
                    SELECT
                        f.resource_id,
                        f.team,
                        f.env,
                        f.provider,
                        COALESCE(f.service_name, 'unknown') AS service_name,
                        CAST(SUM(f.effective_cost) AS DOUBLE PRECISION) AS total_cost,
                        0 AS anomaly_count,
                        0.0 AS risk_score
                    FROM fact_daily_cost f
                    {cost_where}
                    GROUP BY f.resource_id, f.team, f.env, f.provider, service_name
                    ORDER BY total_cost DESC
                    LIMIT %s
                    """,
                    params + [limit],
                )

            rows = cur.fetchall()

    items = [
        {
            "resource_id": r[0],
            "team": r[1],
            "env": r[2],
            "provider": r[3],
            "service_name": r[4],
            "total_cost": round(f(r[5]), 2),
            "anomaly_count": int(r[6]),
            "risk_score": round(f(r[7]), 4) if r[7] is not None else 0.0,
        }
        for r in rows
    ]

    total_cost = sum(i["total_cost"] for i in items)
    total_anomalies = sum(i["anomaly_count"] for i in items)

    return {
        "billing_month": month,
        "items": items,
        "summary": {
            "total_resources": len(items),
            "total_cost": round(total_cost, 2),
            "total_anomalies": total_anomalies,
            "has_anomaly_data": has_anomaly,
        },
    }
