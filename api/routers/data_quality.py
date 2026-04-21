"""Data quality endpoints — check results and CSV export."""
from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..deps import db_read

router = APIRouter(prefix="/api", tags=["data-quality"])

_EXPORTABLE = {
    "fact_daily_cost",
    "anomaly_scores",
    "dim_prophet_forecast",
    "dim_budget_status",
    "dim_chargeback",
    "dim_cost_recommendations",
    "dim_data_quality",
    "dim_fx_rates",
    "pipeline_run_log",
}


@router.get("/data-quality")
def get_data_quality(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    """Return latest data quality check results grouped by table."""
    with db_read() as conn:
        # Check table exists
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_data_quality'"
            )
            if cur.fetchone() is None:
                return {"checks": [], "summary": {"total": 0, "passed": 0, "failed": 0}}

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (table_name, column_name, check_type)
                    id, checked_at, table_name, column_name, check_type,
                    row_count, failed_count, null_ratio, passed, detail
                FROM dim_data_quality
                ORDER BY table_name, column_name, check_type, checked_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()

    checks = []
    for row in rows:
        r = dict(zip(cols, row))
        r["checked_at"] = r["checked_at"].isoformat() if r["checked_at"] else None
        checks.append(r)

    total = len(checks)
    passed = sum(1 for c in checks if c["passed"])
    return {
        "checks": checks,
        "summary": {"total": total, "passed": passed, "failed": total - passed},
    }


@router.get("/export/{table_name}")
def export_table(
    table_name: str,
    limit: int = Query(default=10_000, ge=1, le=100_000),
) -> StreamingResponse:
    """Stream a table as a CSV download (max 100k rows)."""
    if table_name not in _EXPORTABLE:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' is not available for export. "
                   f"Allowed: {sorted(_EXPORTABLE)}",
        )

    with db_read() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f'SELECT * FROM "{table_name}" LIMIT %s',  # noqa: S608
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(cols)
    for row in rows:
        writer.writerow([str(v) if v is not None else "" for v in row])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table_name}.csv"},
    )
