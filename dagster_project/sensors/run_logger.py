"""Pipeline run logger sensor.

Dagster run status sensor로 asset materialize lifecycle을 `pipeline_run_log` 테이블에
기록한다. Dashboard Ops 페이지 / Prometheus metrics가 이 테이블을 읽는다.

Recorded columns:
- run_id        : Dagster run UUID
- asset_key     : materialized asset name
- partition_key : partition (nullable)
- status        : 'started' | 'success' | 'failure'
- started_at    : when the run began
- finished_at   : when the run ended (NULL for 'started')
- duration_sec  : finished_at - started_at (NULL while running)
- row_count     : rows written (NULL if not reported)
- error_message : failure reason (NULL on success)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import psycopg2
from dagster import (
    DagsterRunStatus,
    RunFailureSensorContext,
    RunStatusSensorContext,
    SensorResult,
    run_failure_sensor,
    run_status_sensor,
)

from ..config import load_config
from ..db_schema import ensure_tables

log = logging.getLogger(__name__)


def _conn() -> psycopg2.extensions.connection:
    cfg = load_config()
    c = psycopg2.connect(cfg.postgres.dsn)
    c.autocommit = True
    return c


def _log_event(
    run_id: str,
    asset_key: str | None,
    partition_key: str | None,
    status: str,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    error_message: str | None = None,
) -> None:
    """Insert one pipeline_run_log row. Never raises — logging must not break runs."""
    try:
        conn = _conn()
    except psycopg2.OperationalError:
        log.warning("pipeline_run_log: cannot connect to Postgres — skipping")
        return
    try:
        ensure_tables(conn, "pipeline_run_log")
        dur = None
        if started_at and finished_at:
            dur = (finished_at - started_at).total_seconds()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline_run_log
                    (run_id, asset_key, partition_key, status,
                     started_at, finished_at, duration_sec, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    run_id,
                    asset_key or "<unknown>",
                    partition_key,
                    status,
                    started_at or datetime.now(tz=UTC),
                    finished_at,
                    dur,
                    error_message,
                ],
            )
    except psycopg2.Error as e:
        log.warning("pipeline_run_log insert failed: %s", e)
    finally:
        conn.close()


@run_status_sensor(run_status=DagsterRunStatus.SUCCESS)
def pipeline_run_success_sensor(context: RunStatusSensorContext) -> SensorResult:
    """Record one row per successful run (asset_key = 'job'). Per-asset events
    come from Dagster's asset materialization events, which are visible in the
    UI — we keep this sensor at job granularity to stay lightweight."""
    run = context.dagster_run
    started_at = run.start_time
    finished_at = run.end_time
    started_dt = datetime.fromtimestamp(started_at, tz=UTC) if started_at else None
    finished_dt = datetime.fromtimestamp(finished_at, tz=UTC) if finished_at else None
    _log_event(
        run_id=run.run_id,
        asset_key=run.job_name,
        partition_key=run.tags.get("dagster/partition"),
        status="success",
        started_at=started_dt,
        finished_at=finished_dt,
    )
    return SensorResult(skip_reason=f"logged run {run.run_id}")


@run_failure_sensor
def pipeline_run_failure_sensor(context: RunFailureSensorContext) -> SensorResult:
    """Record one row per failed run with error message."""
    run = context.dagster_run
    started_at = run.start_time
    finished_at = run.end_time
    started_dt = datetime.fromtimestamp(started_at, tz=UTC) if started_at else None
    finished_dt = datetime.fromtimestamp(finished_at, tz=UTC) if finished_at else None
    error = context.failure_event.message or "unknown failure"
    _log_event(
        run_id=run.run_id,
        asset_key=run.job_name,
        partition_key=run.tags.get("dagster/partition"),
        status="failure",
        started_at=started_dt,
        finished_at=finished_dt,
        error_message=error[:2000],
    )
    return SensorResult(skip_reason=f"logged failure {run.run_id}")
