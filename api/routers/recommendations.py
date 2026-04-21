"""GET /api/recommendations — cost optimization suggestions."""

from fastapi import APIRouter

from ..deps import db_read, f, tables
from ..models import RecommendationItem, RecommendationsResponse

router = APIRouter(tags=["recommendations"])


@router.get("/api/recommendations", response_model=RecommendationsResponse)
def get_recommendations() -> RecommendationsResponse:
    with db_read() as db:
        if "dim_cost_recommendations" not in tables(db):
            return RecommendationsResponse(items=[], total_potential_savings=0.0)

        cur = db.cursor()
        cur.execute(
            """
            SELECT recommendation_type, resource_id, team, env,
                   reason, CAST(estimated_savings AS DOUBLE PRECISION), severity
            FROM dim_cost_recommendations
            ORDER BY estimated_savings DESC
            """
        )
        rows = cur.fetchall()
        cur.close()

        items = [
            RecommendationItem(
                rule_type=r[0], resource_id=r[1], team=r[2], env=r[3],
                description=r[4], potential_savings=f(r[5]), severity=r[6],
            )
            for r in rows
        ]

        return RecommendationsResponse(
            items=items,
            total_potential_savings=round(sum(i.potential_savings for i in items), 2),
        )
