"""Alert history endpoints — list dispatched alerts and acknowledge them."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..deps import db_read, db_write

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertItem(BaseModel):
    id: int
    alert_type: str
    severity: str
    resource_id: str
    cost_unit_key: str
    message: str
    actual_cost: float | None
    reference_cost: float | None
    deviation_pct: float | None
    triggered_at: str
    acknowledged: bool
    acknowledged_at: str | None
    acknowledged_by: str | None


class AlertListResponse(BaseModel):
    items: list[AlertItem]
    total: int
    summary: dict[str, Any]


class AcknowledgeRequest(BaseModel):
    acknowledged_by: str = "api"


@router.get("", response_model=AlertListResponse)
def list_alerts(
    severity: str | None = Query(None),
    acknowledged: bool | None = Query(None),
    alert_type: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
) -> AlertListResponse:
    with db_read() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_alert_history'"
            )
            if not cur.fetchone():
                return AlertListResponse(
                    items=[], total=0,
                    summary={"critical": 0, "warning": 0, "info": 0, "unacknowledged": 0},
                )

            filters: list[str] = []
            params: list[Any] = []
            if severity:
                filters.append("severity = %s")
                params.append(severity)
            if acknowledged is not None:
                filters.append("acknowledged = %s")
                params.append(acknowledged)
            if alert_type:
                filters.append("alert_type = %s")
                params.append(alert_type)

            where = ("WHERE " + " AND ".join(filters)) if filters else ""
            cur.execute(
                f"""
                SELECT id, alert_type, severity, resource_id, cost_unit_key,
                       message, actual_cost, reference_cost, deviation_pct,
                       triggered_at, acknowledged, acknowledged_at, acknowledged_by
                FROM dim_alert_history
                {where}
                ORDER BY triggered_at DESC
                LIMIT %s
                """,
                params + [limit],
            )
            rows = cur.fetchall()

            cur.execute(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE severity = 'critical')   AS critical,
                    COUNT(*) FILTER (WHERE severity = 'warning')    AS warning,
                    COUNT(*) FILTER (WHERE severity = 'info')       AS info,
                    COUNT(*) FILTER (WHERE NOT acknowledged)        AS unacknowledged
                FROM dim_alert_history
                {where}
                """,
                params,
            )
            summary_row = cur.fetchone()

    summary: dict[str, Any] = {
        "critical": summary_row[0] if summary_row else 0,
        "warning": summary_row[1] if summary_row else 0,
        "info": summary_row[2] if summary_row else 0,
        "unacknowledged": summary_row[3] if summary_row else 0,
    }

    items = [
        AlertItem(
            id=r[0],
            alert_type=r[1],
            severity=r[2],
            resource_id=r[3],
            cost_unit_key=r[4],
            message=r[5],
            actual_cost=r[6],
            reference_cost=r[7],
            deviation_pct=r[8],
            triggered_at=r[9].isoformat() if hasattr(r[9], "isoformat") else str(r[9]),
            acknowledged=r[10],
            acknowledged_at=(
                r[11].isoformat() if r[11] and hasattr(r[11], "isoformat") else (str(r[11]) if r[11] else None)
            ),
            acknowledged_by=r[12],
        )
        for r in rows
    ]

    return AlertListResponse(items=items, total=len(items), summary=summary)


@router.post("/{alert_id}/acknowledge", response_model=AlertItem)
def acknowledge_alert(
    alert_id: int,
    body: AcknowledgeRequest,
) -> AlertItem:
    now = datetime.now(tz=UTC)
    with db_write() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE dim_alert_history
                SET acknowledged = TRUE,
                    acknowledged_at = %s,
                    acknowledged_by = %s
                WHERE id = %s
                RETURNING id, alert_type, severity, resource_id, cost_unit_key,
                          message, actual_cost, reference_cost, deviation_pct,
                          triggered_at, acknowledged, acknowledged_at, acknowledged_by
                """,
                (now, body.acknowledged_by, alert_id),
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    return AlertItem(
        id=row[0],
        alert_type=row[1],
        severity=row[2],
        resource_id=row[3],
        cost_unit_key=row[4],
        message=row[5],
        actual_cost=row[6],
        reference_cost=row[7],
        deviation_pct=row[8],
        triggered_at=row[9].isoformat() if hasattr(row[9], "isoformat") else str(row[9]),
        acknowledged=row[10],
        acknowledged_at=(
            row[11].isoformat() if row[11] and hasattr(row[11], "isoformat") else None
        ),
        acknowledged_by=row[12],
    )
