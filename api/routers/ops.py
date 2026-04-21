"""Operations endpoints — pipeline run log, liveness/readiness, metrics."""

from __future__ import annotations

from datetime import UTC, datetime

import psycopg2
from fastapi import APIRouter, Query, Response

from ..deps import db_read, tables
from ..models.ops import (
    OpsHealthResponse,
    OpsRunsResponse,
    RunLogEntry,
    TableHealthRow,
)

router = APIRouter(prefix="/api/ops", tags=["ops"])


# ── Tables watched by the Ops page ────────────────────────────────────────────
_WATCHED_TABLES: list[tuple[str, str | None]] = [
    ("fact_daily_cost", "charge_date"),
    ("anomaly_scores", "charge_date"),
    ("dim_forecast", "forecast_generated_at"),
    ("dim_prophet_forecast", None),
    ("dim_budget_status", None),
    ("dim_chargeback", None),
    ("dim_fx_rates", None),
    ("dim_cost_recommendations", None),
    ("pipeline_run_log", "started_at"),
]


@router.get("/runs", response_model=OpsRunsResponse)
def list_runs(limit: int = Query(50, ge=1, le=500)) -> OpsRunsResponse:
    """Most recent Dagster runs from pipeline_run_log."""
    with db_read() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, run_id, asset_key, partition_key, status,
                   started_at, finished_at, duration_sec, row_count, error_message
            FROM pipeline_run_log
            ORDER BY started_at DESC NULLS LAST, id DESC
            LIMIT %s
            """,
            [limit],
        )
        rows = cur.fetchall()
        runs = [
            RunLogEntry(
                id=r[0],
                run_id=r[1],
                asset_key=r[2],
                partition_key=r[3],
                status=r[4],
                started_at=r[5].isoformat() if r[5] else None,
                finished_at=r[6].isoformat() if r[6] else None,
                duration_sec=float(r[7]) if r[7] is not None else None,
                row_count=r[8],
                error_message=r[9],
            )
            for r in rows
        ]

        cur.execute(
            """
            SELECT status, COUNT(*), MAX(finished_at)
            FROM pipeline_run_log
            GROUP BY status
            """
        )
        agg = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
        cur.close()

    success_count, latest_success = agg.get("success", (0, None))
    failure_count, latest_failure = agg.get("failure", (0, None))

    return OpsRunsResponse(
        runs=runs,
        success_count=success_count,
        failure_count=failure_count,
        latest_success_at=latest_success.isoformat() if latest_success else None,
        latest_failure_at=latest_failure.isoformat() if latest_failure else None,
    )


@router.get("/health", response_model=OpsHealthResponse)
def ops_health() -> OpsHealthResponse:
    """Per-table row counts + latest timestamps. Used by the dashboard Ops page."""
    now_iso = datetime.now(tz=UTC).isoformat()
    rows: list[TableHealthRow] = []
    try:
        with db_read() as conn:
            existing = tables(conn)
            cur = conn.cursor()
            for table, ts_col in _WATCHED_TABLES:
                if table not in existing:
                    rows.append(TableHealthRow(table=table, row_count=0, latest_ts=None))
                    continue
                if ts_col:
                    cur.execute(
                        f"SELECT COUNT(*), MAX({ts_col})::TEXT FROM {table}"  # noqa: S608 — hardcoded list
                    )
                else:
                    cur.execute(
                        f"SELECT COUNT(*), NULL::TEXT FROM {table}"  # noqa: S608 — hardcoded list
                    )
                cnt, latest = cur.fetchone()
                rows.append(
                    TableHealthRow(table=table, row_count=int(cnt or 0), latest_ts=latest)
                )
            cur.close()
        db_ok = True
    except psycopg2.Error:
        db_ok = False

    return OpsHealthResponse(db_reachable=db_ok, tables=rows, checked_at=now_iso)


# ── Kubernetes-style liveness & readiness ─────────────────────────────────────

@router.get("/live", tags=["ops"])
def live() -> dict[str, str]:
    """Liveness — process is up. Always 200 unless the worker is dead."""
    return {"status": "alive"}


@router.get("/ready", tags=["ops"])
def ready(response: Response) -> dict[str, object]:
    """Readiness — app can serve traffic. 503 if Postgres is unreachable
    or if the required base tables are missing."""
    required = {
        "fact_daily_cost", "dim_cost_unit", "platform_settings",
        "dim_budget", "pipeline_run_log",
    }
    try:
        with db_read() as conn:
            existing = tables(conn)
        missing = sorted(required - existing)
        if missing:
            response.status_code = 503
            return {"status": "not_ready", "missing_tables": missing}
        return {"status": "ready"}
    except psycopg2.Error as e:
        response.status_code = 503
        return {"status": "not_ready", "error": str(e)}


# ── Prometheus-style text metrics ─────────────────────────────────────────────
# Format: https://prometheus.io/docs/instrumenting/exposition_formats/

@router.get("/metrics", tags=["ops"])
def metrics() -> Response:
    """Minimal Prometheus-compatible metrics snapshot."""
    lines: list[str] = []

    def _push(name: str, help_text: str, value: float, labels: str = "") -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name}{labels} {value}")

    try:
        with db_read() as conn:
            existing = tables(conn)
            cur = conn.cursor()

            if "pipeline_run_log" in existing:
                cur.execute(
                    "SELECT status, COUNT(*) FROM pipeline_run_log GROUP BY status"
                )
                for status, cnt in cur.fetchall():
                    _push(
                        "finops_pipeline_runs_total",
                        "Total pipeline runs by status",
                        float(cnt),
                        labels=f'{{status="{status}"}}',
                    )
                cur.execute(
                    "SELECT AVG(duration_sec) FROM pipeline_run_log "
                    "WHERE finished_at >= NOW() - INTERVAL '1 day'"
                )
                (avg_dur,) = cur.fetchone()
                _push(
                    "finops_pipeline_duration_avg_seconds_24h",
                    "Average pipeline run duration (s) over the last 24h",
                    float(avg_dur) if avg_dur is not None else 0.0,
                )

            for table, _ in _WATCHED_TABLES:
                if table not in existing:
                    continue
                cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 — hardcoded list
                (cnt,) = cur.fetchone()
                _push(
                    "finops_table_rows",
                    "Row count by table",
                    float(cnt),
                    labels=f'{{table="{table}"}}',
                )

            if "anomaly_scores" in existing:
                cur.execute(
                    "SELECT COUNT(*) FROM anomaly_scores "
                    "WHERE is_anomaly AND charge_date >= CURRENT_DATE - INTERVAL '30 days'"
                )
                (cnt,) = cur.fetchone()
                _push(
                    "finops_anomalies_active_30d",
                    "Active anomalies in the last 30 days",
                    float(cnt),
                )

            if "dim_budget_status" in existing:
                cur.execute(
                    "SELECT COUNT(*) FROM dim_budget_status WHERE status = 'over'"
                )
                (cnt,) = cur.fetchone()
                _push(
                    "finops_budgets_over",
                    "Number of over-budget (team,env) this month",
                    float(cnt),
                )

            cur.close()
        _push(
            "finops_database_up",
            "Database reachability (1 = up, 0 = down)",
            1.0,
        )
    except psycopg2.Error:
        _push(
            "finops_database_up",
            "Database reachability (1 = up, 0 = down)",
            0.0,
        )

    body = "\n".join(lines) + "\n"
    return Response(content=body, media_type="text/plain; version=0.0.4")
