"""Pydantic models for /api/ops/* endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class RunLogEntry(BaseModel):
    id: int
    run_id: str
    asset_key: str
    partition_key: str | None
    status: str
    started_at: str | None
    finished_at: str | None
    duration_sec: float | None
    row_count: int | None
    error_message: str | None


class OpsRunsResponse(BaseModel):
    runs: list[RunLogEntry]
    success_count: int
    failure_count: int
    latest_success_at: str | None
    latest_failure_at: str | None


class TableHealthRow(BaseModel):
    table: str
    row_count: int
    latest_ts: str | None


class OpsHealthResponse(BaseModel):
    db_reachable: bool
    tables: list[TableHealthRow]
    checked_at: str
