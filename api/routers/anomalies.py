"""GET /api/anomalies — z-score / IF / MA anomalies with optional severity filter."""

from fastapi import APIRouter, Query

from ..deps import columns, db_read, f, tables
from ..models import AnomaliesResponse, AnomalyItem

router = APIRouter(tags=["anomalies"])

_ALLOWED_SEVERITIES = {"critical", "warning"}


@router.get("/api/anomalies", response_model=AnomaliesResponse)
def get_anomalies(
    severity: str | None = Query(None, description="critical | warning"),
    team: str | None = Query(None),
    env: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> AnomaliesResponse:
    with db_read() as db:
        if "anomaly_scores" not in tables(db):
            return AnomaliesResponse(items=[], total=0, critical=0, warning=0)

        cur = db.cursor()

        where = ["is_anomaly = true"]
        params: list[object] = []
        if severity and severity in _ALLOWED_SEVERITIES:
            where.append("severity = %s")
            params.append(severity)
        if team:
            where.append("team = %s")
            params.append(team)
        if env:
            where.append("env = %s")
            params.append(env)
        where_clause = "WHERE " + " AND ".join(where)

        has_detector = "detector_name" in columns(db, "anomaly_scores")
        detector_col = "detector_name" if has_detector else "'zscore' AS detector_name"

        cur.execute(
            f"""
            SELECT resource_id, cost_unit_key, team, product, env,
                   charge_date::TEXT,
                   CAST(effective_cost AS DOUBLE PRECISION),
                   CAST(z_score AS DOUBLE PRECISION),
                   severity, {detector_col}
            FROM anomaly_scores
            {where_clause}
            ORDER BY charge_date DESC, z_score DESC
            LIMIT {limit}
            """,
            params,
        )
        rows = cur.fetchall()

        cur.execute(
            "SELECT severity, COUNT(*) FROM anomaly_scores WHERE is_anomaly = true GROUP BY severity"
        )
        counts = cur.fetchall()
        count_map = {r[0]: r[1] for r in counts}

        cur.close()

        items = [
            AnomalyItem(
                resource_id=r[0], cost_unit_key=r[1], team=r[2], product=r[3],
                env=r[4], charge_date=r[5], effective_cost=f(r[6]),
                z_score=f(r[7]), severity=r[8], detector_name=r[9],
            )
            for r in rows
        ]

        return AnomaliesResponse(
            items=items,
            total=count_map.get("critical", 0) + count_map.get("warning", 0),
            critical=count_map.get("critical", 0),
            warning=count_map.get("warning", 0),
        )
