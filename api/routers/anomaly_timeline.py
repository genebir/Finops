"""GET /api/anomaly-timeline — daily anomaly count time series."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/anomaly-timeline", tags=["anomaly-timeline"])


@router.get("")
def anomaly_timeline(
    months: int = Query(6, ge=1, le=24),
    provider: str | None = Query(None),
    team: str | None = Query(None),
    severity: str | None = Query(None),
) -> dict[str, Any]:
    with db_read() as conn:
        with conn.cursor() as cur:
            # anchor to max charge_date in anomaly_scores
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='anomaly_scores'"
            )
            if not cur.fetchone():
                return {"months": months, "series": [], "summary": {"total_anomalies": 0, "peak_date": None, "peak_count": 0, "avg_daily": 0.0}}

            cur.execute("SELECT MAX(charge_date) FROM anomaly_scores WHERE is_anomaly = TRUE")
            row = cur.fetchone()
            if not row or not row[0]:
                return {"months": months, "series": [], "summary": {"total_anomalies": 0, "peak_date": None, "peak_count": 0, "avg_daily": 0.0}}
            anchor = row[0]

            filters = [
                "a.is_anomaly = TRUE",
                "a.charge_date >= %s - (%s * INTERVAL '30 days')",
            ]
            params: list[Any] = [anchor, months]

            if provider:
                filters.append(
                    "a.resource_id IN (SELECT DISTINCT resource_id FROM fact_daily_cost WHERE provider = %s)"
                )
                params.append(provider)
            if team:
                filters.append("a.team = %s")
                params.append(team)
            if severity:
                filters.append("a.severity = %s")
                params.append(severity)

            where = "WHERE " + " AND ".join(filters)

            cur.execute(
                f"""
                SELECT a.charge_date::TEXT,
                       COUNT(*)                                         AS total_count,
                       COUNT(*) FILTER (WHERE a.severity = 'critical') AS critical_count,
                       COUNT(*) FILTER (WHERE a.severity = 'warning')  AS warning_count,
                       CAST(SUM(a.effective_cost) AS DOUBLE PRECISION) AS total_cost
                FROM anomaly_scores a
                {where}
                GROUP BY a.charge_date
                ORDER BY a.charge_date
                """,
                params,
            )
            daily_rows = cur.fetchall()

            # top resources on worst day
            peak_date = None
            peak_count = 0
            if daily_rows:
                peak_row = max(daily_rows, key=lambda r: r[1])
                peak_date = peak_row[0]
                peak_count = int(peak_row[1])

            # top impacted teams (overall)
            cur.execute(
                f"""
                SELECT a.team,
                       COUNT(*) AS anomaly_count,
                       CAST(SUM(a.effective_cost) AS DOUBLE PRECISION) AS total_cost
                FROM anomaly_scores a
                {where}
                GROUP BY a.team
                ORDER BY anomaly_count DESC
                LIMIT 5
                """,
                params,
            )
            team_rows = cur.fetchall()

    series = [
        {
            "date": r[0],
            "total": int(r[1]),
            "critical": int(r[2]),
            "warning": int(r[3]),
            "total_cost": round(f(r[4]), 2),
        }
        for r in daily_rows
    ]

    total_anomalies = sum(s["total"] for s in series)
    avg_daily = round(total_anomalies / len(series), 2) if series else 0.0

    top_teams = [
        {"team": r[0], "anomaly_count": int(r[1]), "total_cost": round(f(r[2]), 2)}
        for r in team_rows
    ]

    return {
        "months": months,
        "series": series,
        "top_teams": top_teams,
        "summary": {
            "total_anomalies": total_anomalies,
            "peak_date": peak_date,
            "peak_count": peak_count,
            "avg_daily": avg_daily,
        },
    }
