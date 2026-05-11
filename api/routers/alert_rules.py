"""Alert rules CRUD — custom thresholds per team/resource/metric."""
from __future__ import annotations

from typing import Any, Literal

import psycopg2
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..deps import db_read, db_write
from dagster_project.db_schema import ensure_tables

router = APIRouter(prefix="/api/alert-rules", tags=["alert-rules"])

_ALLOWED_METRICS = ("cost_spike", "anomaly_count", "budget_pct")
_ALLOWED_SEVERITIES = ("warning", "critical")

_COLS = (
    "id",
    "rule_name",
    "team",
    "resource_id",
    "metric",
    "threshold",
    "severity",
    "enabled",
    "created_at",
)


class AlertRuleCreate(BaseModel):
    rule_name: str = Field(min_length=1, max_length=200)
    team: str | None = None
    resource_id: str | None = None
    metric: Literal["cost_spike", "anomaly_count", "budget_pct"]
    threshold: float = Field(gt=0)
    severity: Literal["warning", "critical"] = "warning"
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    team: str | None = None
    resource_id: str | None = None
    metric: Literal["cost_spike", "anomaly_count", "budget_pct"] | None = None
    threshold: float | None = Field(default=None, gt=0)
    severity: Literal["warning", "critical"] | None = None
    enabled: bool | None = None


def _row_to_dict(row: tuple) -> dict[str, Any]:
    d: dict[str, Any] = dict(zip(_COLS, row))
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    return d


@router.get("")
def list_rules(
    team: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
) -> dict[str, Any]:
    with db_read() as conn:
        ensure_tables(conn, "dim_alert_rules")
        clauses: list[str] = []
        params: list[Any] = []
        if team is not None:
            clauses.append("team = %s")
            params.append(team)
        if enabled is not None:
            clauses.append("enabled = %s")
            params.append(enabled)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, rule_name, team, resource_id, metric, threshold,
                       severity, enabled, created_at
                FROM dim_alert_rules
                {where}
                ORDER BY id
                """,  # noqa: S608
                params,
            )
            rows = cur.fetchall()

    items = [_row_to_dict(r) for r in rows]
    return {
        "items": items,
        "total": len(items),
        "summary": {
            "total": len(items),
            "enabled": sum(1 for it in items if it["enabled"]),
            "disabled": sum(1 for it in items if not it["enabled"]),
        },
    }


@router.post("", status_code=201)
def create_rule(body: AlertRuleCreate) -> dict[str, Any]:
    with db_write() as conn:
        ensure_tables(conn, "dim_alert_rules")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dim_alert_rules
                        (rule_name, team, resource_id, metric, threshold, severity, enabled)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, rule_name, team, resource_id, metric, threshold,
                              severity, enabled, created_at
                    """,
                    (
                        body.rule_name,
                        body.team,
                        body.resource_id,
                        body.metric,
                        body.threshold,
                        body.severity,
                        body.enabled,
                    ),
                )
                row = cur.fetchone()
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail=f"Rule name '{body.rule_name}' already exists")
    if row is None:
        raise HTTPException(status_code=500, detail="Insert failed")
    return _row_to_dict(row)


@router.put("/{rule_id}")
def update_rule(rule_id: int, body: AlertRuleUpdate) -> dict[str, Any]:
    sets: list[str] = []
    params: list[Any] = []
    for field in ("team", "resource_id", "metric", "threshold", "severity", "enabled"):
        value = getattr(body, field)
        if value is not None:
            sets.append(f"{field} = %s")
            params.append(value)
    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")
    params.append(rule_id)
    with db_write() as conn:
        ensure_tables(conn, "dim_alert_rules")
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE dim_alert_rules
                SET {", ".join(sets)}
                WHERE id = %s
                RETURNING id, rule_name, team, resource_id, metric, threshold,
                          severity, enabled, created_at
                """,  # noqa: S608
                params,
            )
            row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return _row_to_dict(row)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int) -> None:
    with db_write() as conn:
        ensure_tables(conn, "dim_alert_rules")
        with conn.cursor() as cur:
            cur.execute("DELETE FROM dim_alert_rules WHERE id = %s", (rule_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
