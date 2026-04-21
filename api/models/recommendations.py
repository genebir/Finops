"""Recommendations response models."""

from pydantic import BaseModel


class RecommendationItem(BaseModel):
    rule_type: str
    resource_id: str
    team: str
    env: str
    description: str
    potential_savings: float
    severity: str


class RecommendationsResponse(BaseModel):
    items: list[RecommendationItem]
    total_potential_savings: float
