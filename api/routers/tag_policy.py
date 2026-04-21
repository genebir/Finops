"""Tag policy violations endpoint."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read

router = APIRouter(prefix="/api", tags=["tag-policy"])


@router.get("/tag-policy")
def get_tag_violations(
    severity: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    missing_tag: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    """Return today's tag policy violations."""
    with db_read() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_tag_violations'"
            )
            if cur.fetchone() is None:
                return {
                    "violations": [],
                    "summary": {"total": 0, "critical": 0, "warning": 0},
                }

        clauses: list[str] = []
        params: list[Any] = []

        # Always scope to latest detection day
        clauses.append(
            "detected_at >= CURRENT_DATE"
        )

        if severity:
            clauses.append("severity = %s")
            params.append(severity)
        if provider:
            clauses.append("provider = %s")
            params.append(provider)
        if missing_tag:
            clauses.append("missing_tag = %s")
            params.append(missing_tag)

        where = "WHERE " + " AND ".join(clauses)
        params_limited = params + [limit]

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, resource_id, resource_type, service_category,
                       provider, team, env, violation_type, missing_tag,
                       severity, cost_30d, detected_at
                FROM dim_tag_violations
                {where}
                ORDER BY cost_30d DESC NULLS LAST
                LIMIT %s
                """,  # noqa: S608
                params_limited,
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*),
                       SUM(CASE WHEN severity='critical' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN severity='warning' THEN 1 ELSE 0 END)
                FROM dim_tag_violations {where}
                """,  # noqa: S608
                params,
            )
            total, crit, warn = cur.fetchone()

    violations = []
    for row in rows:
        r = dict(zip(cols, row))
        if r.get("detected_at"):
            r["detected_at"] = r["detected_at"].isoformat()
        violations.append(r)

    return {
        "violations": violations,
        "summary": {
            "total": total or 0,
            "critical": crit or 0,
            "warning": warn or 0,
        },
    }
