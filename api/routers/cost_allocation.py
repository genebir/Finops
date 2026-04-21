"""Cost allocation rules CRUD + allocated cost view."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..deps import db_read, db_write

router = APIRouter(prefix="/api/cost-allocation", tags=["cost-allocation"])

_RULES_DDL = """
CREATE TABLE IF NOT EXISTS dim_allocation_rules (
    id           BIGSERIAL        PRIMARY KEY,
    resource_id  VARCHAR          NOT NULL,
    team         VARCHAR          NOT NULL,
    split_pct    DOUBLE PRECISION NOT NULL,
    description  VARCHAR,
    created_at   TIMESTAMPTZ      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT allocation_pct_range CHECK (split_pct > 0 AND split_pct <= 100)
)
"""


class AllocationRuleCreate(BaseModel):
    resource_id: str
    team: str
    split_pct: float = Field(gt=0, le=100)
    description: str | None = None


class AllocationRuleUpdate(BaseModel):
    split_pct: float = Field(gt=0, le=100)
    description: str | None = None


def _ensure_rules_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_RULES_DDL)


@router.get("/rules")
def list_rules() -> dict[str, Any]:
    with db_read() as conn:
        _ensure_rules_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, resource_id, team, split_pct, description, created_at FROM dim_allocation_rules ORDER BY resource_id, team"
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()

    items = []
    for row in rows:
        r = dict(zip(cols, row))
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
        items.append(r)
    return {"items": items}


@router.post("/rules", status_code=201)
def create_rule(body: AllocationRuleCreate) -> dict[str, Any]:
    with db_write() as conn:
        _ensure_rules_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dim_allocation_rules (resource_id, team, split_pct, description)
                VALUES (%s, %s, %s, %s)
                RETURNING id, resource_id, team, split_pct, description, created_at
                """,
                (body.resource_id, body.team, body.split_pct, body.description),
            )
            cols = [d[0] for d in cur.description]
            row = dict(zip(cols, cur.fetchone()))
    if row.get("created_at"):
        row["created_at"] = row["created_at"].isoformat()
    return row


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, body: AllocationRuleUpdate) -> dict[str, Any]:
    with db_write() as conn:
        _ensure_rules_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE dim_allocation_rules SET split_pct=%s, description=%s
                WHERE id=%s
                RETURNING id, resource_id, team, split_pct, description, created_at
                """,
                (body.split_pct, body.description, rule_id),
            )
            row_raw = cur.fetchone()
    if not row_raw:
        raise HTTPException(status_code=404, detail="Rule not found")
    return dict(zip(["id", "resource_id", "team", "split_pct", "description", "created_at"], row_raw))


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int) -> None:
    with db_write() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM dim_allocation_rules WHERE id=%s", (rule_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Rule not found")


@router.get("")
def get_allocated_costs(
    team: str | None = Query(default=None),
    billing_month: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    """Return allocated costs, grouped by team if no filter."""
    import datetime
    month = billing_month or datetime.date.today().strftime("%Y-%m")

    with db_read() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_allocated_cost'"
            )
            if cur.fetchone() is None:
                return {"items": [], "billing_month": month, "total_allocated": 0}

        clauses = ["to_char(charge_date, 'YYYY-MM') = %s"]
        params: list[Any] = [month]
        if team:
            clauses.append("allocated_team = %s")
            params.append(team)

        where = "WHERE " + " AND ".join(clauses)
        params.append(limit)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT allocated_team, resource_id, resource_name, service_name,
                       provider, split_pct, allocation_type,
                       ROUND(CAST(SUM(allocated_cost) AS NUMERIC), 2) AS total_allocated,
                       ROUND(CAST(SUM(original_cost) AS NUMERIC), 2) AS total_original
                FROM dim_allocated_cost
                {where}
                GROUP BY allocated_team, resource_id, resource_name, service_name,
                         provider, split_pct, allocation_type
                ORDER BY total_allocated DESC
                LIMIT %s
                """,  # noqa: S608
                params,
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()

    items = [dict(zip(cols, r)) for r in rows]
    total = sum(float(r.get("total_allocated") or 0) for r in items)
    return {"items": items, "billing_month": month, "total_allocated": round(total, 2)}
