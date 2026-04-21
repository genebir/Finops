"""GET /api/resources/{resource_id} — per-resource cost drill-down."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..deps import db_read, f, tables

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("/{resource_id}")
def resource_detail(
    resource_id: str,
    months: int = Query(6, ge=1, le=36, description="Number of months of history"),
) -> dict[str, Any]:
    with db_read() as conn:
        with conn.cursor() as cur:
            # Anchor to latest date in the table (data may be historical)
            cur.execute("SELECT MAX(charge_date) FROM fact_daily_cost WHERE resource_id = %s", (resource_id,))
            anchor_row = cur.fetchone()
            if not anchor_row or anchor_row[0] is None:
                raise HTTPException(status_code=404, detail=f"Resource '{resource_id}' not found")
            anchor_date = anchor_row[0]

            # Monthly cost history
            cur.execute(
                """
                SELECT to_char(charge_date, 'YYYY-MM') AS billing_month,
                       CAST(SUM(effective_cost) AS DOUBLE PRECISION)  AS cost,
                       COALESCE(MAX(provider), 'unknown')             AS provider,
                       COALESCE(MAX(service_name), 'unknown')         AS service_name,
                       COALESCE(MAX(team), 'unknown')                 AS team,
                       COALESCE(MAX(env), 'unknown')                  AS env
                FROM fact_daily_cost
                WHERE resource_id = %s
                  AND charge_date >= %s - (%s * INTERVAL '30 days')
                GROUP BY billing_month
                ORDER BY billing_month DESC
                LIMIT %s
                """,
                (resource_id, anchor_date, months, months),
            )
            month_rows = cur.fetchall()

        # Daily cost (last 30 days from anchor)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT charge_date::TEXT,
                       CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS cost
                FROM fact_daily_cost
                WHERE resource_id = %s
                  AND charge_date >= %s - INTERVAL '30 days'
                GROUP BY charge_date
                ORDER BY charge_date
                """,
                (resource_id, anchor_date),
            )
            daily_rows = cur.fetchall()

        # Anomaly history
        anomaly_history: list[dict[str, Any]] = []
        if "anomaly_scores" in tables(conn):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT charge_date::TEXT, z_score, severity, detector_name,
                           CAST(effective_cost AS DOUBLE PRECISION),
                           CAST(mean_cost AS DOUBLE PRECISION)
                    FROM anomaly_scores
                    WHERE resource_id = %s
                      AND is_anomaly = TRUE
                    ORDER BY charge_date DESC LIMIT 20
                    """,
                    (resource_id,),
                )
                for r in cur.fetchall():
                    anomaly_history.append({
                        "date": r[0], "z_score": round(f(r[1]), 2),
                        "severity": r[2], "detector_name": r[3],
                        "effective_cost": round(f(r[4]), 2),
                        "mean_cost": round(f(r[5]), 2),
                    })

    latest = month_rows[0]
    monthly = [
        {
            "billing_month": r[0],
            "cost": round(f(r[1]), 2),
            "provider": r[2],
            "service_name": r[3],
            "team": r[4],
            "env": r[5],
        }
        for r in reversed(month_rows)
    ]

    daily = [{"date": r[0], "cost": round(f(r[1]), 2)} for r in daily_rows]

    total_cost = sum(m["cost"] for m in monthly)
    avg_monthly = total_cost / len(monthly) if monthly else 0.0

    return {
        "resource_id": resource_id,
        "provider": latest[2],
        "service_name": latest[3],
        "team": latest[4],
        "env": latest[5],
        "monthly_history": monthly,
        "daily_last30": daily,
        "anomaly_history": anomaly_history,
        "summary": {
            "total_cost": round(total_cost, 2),
            "avg_monthly_cost": round(avg_monthly, 2),
            "latest_month_cost": round(f(latest[1]), 2),
            "anomaly_count": len(anomaly_history),
            "months_tracked": len(monthly),
        },
    }
