"""Budget endpoints — read status view + CRUD on dim_budget entries.

GET    /api/budget            → computed status (budget vs actual, used_pct, status)
GET    /api/budget/entries    → raw dim_budget rows (for CRUD UI)
POST   /api/budget            → create a new budget entry
PUT    /api/budget/{team}/{env}  → update budget_amount
DELETE /api/budget/{team}/{env}  → remove budget entry
"""

from fastapi import APIRouter, HTTPException, Query

from ..deps import columns, db_read, db_write, f, tables
from ..models import (
    BudgetCreateRequest,
    BudgetEntry,
    BudgetEntryListResponse,
    BudgetItem,
    BudgetResponse,
    BudgetUpdateRequest,
)

router = APIRouter(tags=["budget"])

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dim_budget (
    team           VARCHAR NOT NULL,
    env            VARCHAR NOT NULL,
    budget_amount  DECIMAL(18, 6) NOT NULL,
    billing_month  VARCHAR NOT NULL DEFAULT 'default',
    updated_at     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (team, env, billing_month)
)
"""


# ── Read: computed status ────────────────────────────────────────────────────

@router.get("/api/budget", response_model=BudgetResponse)
def get_budget() -> BudgetResponse:
    """Returns budget status (used_pct, status) — joined from dim_budget_status."""
    with db_read() as db:
        cur = db.cursor()
        _tables = tables(db)
        if "dim_budget_status" not in _tables:
            cur.execute(
                """
                SELECT team, env, CAST(SUM(effective_cost) AS DOUBLE PRECISION)
                FROM fact_daily_cost GROUP BY team, env ORDER BY 3 DESC
                """
            )
            team_rows = cur.fetchall()
            cur.close()
            items = [
                BudgetItem(
                    team=r[0], env=r[1], budget_amount=0.0,
                    actual_cost=f(r[2]), used_pct=0.0, status="unknown",
                )
                for r in team_rows
            ]
            return BudgetResponse(
                items=items, total_budget=0.0,
                total_actual=sum(i.actual_cost for i in items),
            )

        cols = columns(db, "dim_budget_status")
        pct_col = "utilization_pct" if "utilization_pct" in cols else "used_pct"
        status_col = "status" if "status" in cols else (
            f"CASE WHEN {pct_col} >= 100 THEN 'over' "
            f"     WHEN {pct_col} >= 80 THEN 'warning' "
            "     ELSE 'ok' END"
        )

        cur.execute(
            f"""
            SELECT team, env,
                   CAST(budget_amount AS DOUBLE PRECISION),
                   CAST(actual_cost AS DOUBLE PRECISION),
                   CAST({pct_col} AS DOUBLE PRECISION),
                   {status_col}
            FROM dim_budget_status
            ORDER BY {pct_col} DESC
            """
        )
        rows = cur.fetchall()
        cur.close()

        items = [
            BudgetItem(
                team=r[0], env=r[1], budget_amount=f(r[2]),
                actual_cost=f(r[3]), used_pct=f(r[4]), status=r[5],
            )
            for r in rows
        ]

        return BudgetResponse(
            items=items,
            total_budget=sum(i.budget_amount for i in items),
            total_actual=sum(i.actual_cost for i in items),
        )


# ── Read: raw entries ────────────────────────────────────────────────────────

@router.get("/api/budget/entries", response_model=BudgetEntryListResponse)
def list_budget_entries(
    billing_month: str | None = Query(None, description="Filter by billing month"),
) -> BudgetEntryListResponse:
    """Raw dim_budget rows — used by the CRUD UI."""
    with db_read() as db:
        if "dim_budget" not in tables(db):
            return BudgetEntryListResponse(items=[])

        cur = db.cursor()
        if billing_month:
            cur.execute(
                "SELECT team, env, CAST(budget_amount AS DOUBLE PRECISION), billing_month "
                "FROM dim_budget WHERE billing_month = %s ORDER BY team, env",
                [billing_month],
            )
        else:
            cur.execute(
                "SELECT team, env, CAST(budget_amount AS DOUBLE PRECISION), billing_month "
                "FROM dim_budget ORDER BY billing_month DESC, team, env"
            )
        rows = cur.fetchall()
        cur.close()

        return BudgetEntryListResponse(
            items=[
                BudgetEntry(team=r[0], env=r[1], budget_amount=f(r[2]), billing_month=r[3])
                for r in rows
            ]
        )


# ── Create ───────────────────────────────────────────────────────────────────

@router.post("/api/budget", response_model=BudgetEntry, status_code=201)
def create_budget_entry(body: BudgetCreateRequest) -> BudgetEntry:
    """Create a new budget entry. Conflicts on (team, env, billing_month) → 409."""
    with db_write() as db:
        cur = db.cursor()
        cur.execute(_CREATE_TABLE_SQL)
        cur.execute(
            "SELECT 1 FROM dim_budget WHERE team=%s AND env=%s AND billing_month=%s",
            [body.team, body.env, body.billing_month],
        )
        if cur.fetchone():
            cur.close()
            raise HTTPException(
                status_code=409,
                detail=f"Budget for ({body.team}, {body.env}, {body.billing_month}) already exists. Use PUT to update.",
            )
        cur.execute(
            "INSERT INTO dim_budget (team, env, budget_amount, billing_month) VALUES (%s, %s, %s, %s)",
            [body.team, body.env, body.budget_amount, body.billing_month],
        )
        cur.close()
        return BudgetEntry(
            team=body.team, env=body.env,
            budget_amount=body.budget_amount,
            billing_month=body.billing_month,
        )


# ── Update ───────────────────────────────────────────────────────────────────

@router.put("/api/budget/{team}/{env}", response_model=BudgetEntry)
def update_budget_entry(
    team: str,
    env: str,
    body: BudgetUpdateRequest,
    billing_month: str = Query("default"),
) -> BudgetEntry:
    """Update budget_amount for an existing entry."""
    with db_write() as db:
        cur = db.cursor()
        cur.execute(_CREATE_TABLE_SQL)
        cur.execute(
            "SELECT 1 FROM dim_budget WHERE team=%s AND env=%s AND billing_month=%s",
            [team, env, billing_month],
        )
        if not cur.fetchone():
            cur.close()
            raise HTTPException(
                status_code=404,
                detail=f"No budget entry for ({team}, {env}, {billing_month}).",
            )
        cur.execute(
            "UPDATE dim_budget SET budget_amount=%s, updated_at=NOW() "
            "WHERE team=%s AND env=%s AND billing_month=%s",
            [body.budget_amount, team, env, billing_month],
        )
        cur.close()
        return BudgetEntry(
            team=team, env=env,
            budget_amount=body.budget_amount,
            billing_month=billing_month,
        )


# ── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/api/budget/{team}/{env}", status_code=204)
def delete_budget_entry(
    team: str,
    env: str,
    billing_month: str = Query("default"),
) -> None:
    """Delete a budget entry."""
    with db_write() as db:
        if "dim_budget" not in tables(db):
            raise HTTPException(status_code=404, detail="dim_budget table does not exist")
        cur = db.cursor()
        cur.execute(
            "SELECT 1 FROM dim_budget WHERE team=%s AND env=%s AND billing_month=%s",
            [team, env, billing_month],
        )
        if not cur.fetchone():
            cur.close()
            raise HTTPException(
                status_code=404,
                detail=f"No budget entry for ({team}, {env}, {billing_month}).",
            )
        cur.execute(
            "DELETE FROM dim_budget WHERE team=%s AND env=%s AND billing_month=%s",
            [team, env, billing_month],
        )
        cur.close()
