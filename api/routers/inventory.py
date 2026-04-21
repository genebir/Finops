"""Resource inventory endpoint."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read

router = APIRouter(prefix="/api", tags=["inventory"])


@router.get("/inventory")
def get_inventory(
    provider: str | None = Query(default=None),
    team: str | None = Query(default=None),
    env: str | None = Query(default=None),
    tags_complete: bool | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    """Return resource inventory with optional filters."""
    with db_read() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_resource_inventory'"
            )
            if cur.fetchone() is None:
                return {"items": [], "summary": {"total": 0, "complete": 0, "incomplete": 0}}

        clauses = []
        params: list[Any] = []
        if provider:
            clauses.append("provider = %s")
            params.append(provider)
        if team:
            clauses.append("team = %s")
            params.append(team)
        if env:
            clauses.append("env = %s")
            params.append(env)
        if tags_complete is not None:
            clauses.append("tags_complete = %s")
            params.append(tags_complete)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT resource_id, resource_name, resource_type, service_name,
                       service_category, region_id, provider, team, product, env,
                       cost_unit_key, first_seen_date, last_seen_date,
                       total_cost_30d, tags_complete, missing_tags, refreshed_at
                FROM dim_resource_inventory
                {where}
                ORDER BY total_cost_30d DESC
                LIMIT %s
                """,  # noqa: S608
                params,
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()

        # Summary counts
        with conn.cursor() as cur:
            base_where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            cur.execute(
                f"""
                SELECT COUNT(*),
                       SUM(CASE WHEN tags_complete THEN 1 ELSE 0 END),
                       SUM(CASE WHEN NOT tags_complete THEN 1 ELSE 0 END)
                FROM dim_resource_inventory {base_where}
                """,  # noqa: S608
                params[:-1],  # exclude limit
            )
            total, complete, incomplete = cur.fetchone()

    items = []
    for row in rows:
        r = dict(zip(cols, row))
        for k in ("first_seen_date", "last_seen_date"):
            if r.get(k):
                r[k] = r[k].isoformat()
        if r.get("refreshed_at"):
            r["refreshed_at"] = r["refreshed_at"].isoformat()
        items.append(r)

    return {
        "items": items,
        "summary": {
            "total": total or 0,
            "complete": complete or 0,
            "incomplete": incomplete or 0,
            "completeness_pct": round((complete or 0) / (total or 1) * 100, 1),
        },
    }
