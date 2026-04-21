"""GET /api/tag-compliance — 팀·프로바이더별 태그 준수율 점수."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..deps import db_read, f

router = APIRouter(prefix="/api/tag-compliance", tags=["tag-compliance"])

_DDL = """
CREATE TABLE IF NOT EXISTS dim_tag_compliance (
    billing_month       VARCHAR          NOT NULL,
    team                VARCHAR          NOT NULL,
    provider            VARCHAR          NOT NULL,
    total_resources     BIGINT           NOT NULL,
    tagged_resources    BIGINT           NOT NULL,
    violation_count     INTEGER          NOT NULL DEFAULT 0,
    tag_completeness    DOUBLE PRECISION NOT NULL,
    compliance_score    DOUBLE PRECISION NOT NULL,
    rank                INTEGER,
    computed_at         TIMESTAMPTZ      NOT NULL,
    PRIMARY KEY (billing_month, team, provider)
)
"""


@router.get("")
def tag_compliance(
    billing_month: str | None = Query(None),
    provider: str | None = Query(None),
    team: str | None = Query(None),
) -> dict[str, Any]:
    with db_read() as conn:
        with conn.cursor() as cur:
            cur.execute(_DDL)
            # resolve latest month
            if billing_month:
                month = billing_month
            else:
                cur.execute(
                    "SELECT MAX(billing_month) FROM dim_tag_compliance"
                )
                row = cur.fetchone()
                if not row or not row[0]:
                    return {
                        "billing_month": "n/a",
                        "summary": {"avg_score": 0, "perfect_count": 0, "below_threshold_count": 0, "total_teams": 0},
                        "teams": [],
                    }
                month = row[0]

            filters = ["billing_month = %s"]
            params: list[Any] = [month]
            if provider:
                filters.append("provider = %s")
                params.append(provider)
            if team:
                filters.append("team = %s")
                params.append(team)
            where = "WHERE " + " AND ".join(filters)

            cur.execute(
                f"""
                SELECT team, provider,
                       total_resources, tagged_resources, violation_count,
                       tag_completeness, compliance_score, rank
                FROM dim_tag_compliance
                {where}
                ORDER BY compliance_score DESC, team
                """,
                params,
            )
            rows = cur.fetchall()

    teams = [
        {
            "team": r[0],
            "provider": r[1],
            "total_resources": int(r[2]),
            "tagged_resources": int(r[3]),
            "violation_count": int(r[4]),
            "tag_completeness": round(f(r[5]), 1),
            "compliance_score": round(f(r[6]), 1),
            "rank": r[7],
        }
        for r in rows
    ]

    scores = [t["compliance_score"] for t in teams]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    perfect_count = sum(1 for s in scores if s >= 99.9)
    below_threshold_count = sum(1 for s in scores if s < 70.0)

    return {
        "billing_month": month,
        "summary": {
            "avg_score": avg_score,
            "perfect_count": perfect_count,
            "below_threshold_count": below_threshold_count,
            "total_teams": len({t["team"] for t in teams}),
        },
        "teams": teams,
    }
