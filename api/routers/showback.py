"""Showback report endpoints."""
from __future__ import annotations

import datetime
import json
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ..deps import db_read

router = APIRouter(prefix="/api/showback", tags=["showback"])


def _table_exists(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_showback_report'"
        )
        return cur.fetchone() is not None


@router.get("")
def get_showback(
    billing_month: str | None = Query(default=None),
    team: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return latest showback report data."""
    month = billing_month or datetime.date.today().strftime("%Y-%m")

    with db_read() as conn:
        if not _table_exists(conn):
            return {"billing_month": month, "teams": [], "generated_at": None}

        clauses = ["billing_month = %s"]
        params: list[Any] = [month]
        if team:
            clauses.append("team = %s")
            params.append(team)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT team, total_cost, budget_amount, utilization_pct,
                       anomaly_count, top_services, top_resources, generated_at
                FROM dim_showback_report
                WHERE {" AND ".join(clauses)}
                ORDER BY total_cost DESC
                """,  # noqa: S608
                params,
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()

    teams = []
    generated_at = None
    for row in rows:
        r = dict(zip(cols, row))
        if r.get("generated_at"):
            generated_at = r["generated_at"].isoformat()
            r["generated_at"] = generated_at
        # top_services/top_resources may be returned as string or dict from psycopg2+jsonb
        for key in ("top_services", "top_resources"):
            val = r.get(key)
            if isinstance(val, str):
                try:
                    r[key] = json.loads(val)
                except json.JSONDecodeError:
                    r[key] = []
            elif val is None:
                r[key] = []
        teams.append(r)

    total = sum(t["total_cost"] for t in teams)
    return {
        "billing_month": month,
        "teams": teams,
        "total_cost": round(total, 2),
        "generated_at": generated_at,
    }


@router.get("/export")
def export_showback(
    billing_month: str | None = Query(default=None),
    team: str | None = Query(default=None),
) -> JSONResponse:
    """Export showback report as a JSON file download."""
    data = get_showback(billing_month=billing_month, team=team)
    filename = f"showback_{data['billing_month']}"
    if team:
        filename += f"_{team}"
    filename += ".json"

    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
