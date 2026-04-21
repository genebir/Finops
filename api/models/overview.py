"""Overview response models."""

from pydantic import BaseModel


class TeamCost(BaseModel):
    team: str
    cost: float
    pct: float


class TopResource(BaseModel):
    resource_id: str
    resource_name: str | None
    service_name: str | None
    region_id: str | None
    team: str
    product: str
    env: str
    cost: float
    active_days: int


class OverviewResponse(BaseModel):
    period_start: str
    period_end: str
    total_cost: float
    cost_by_team: list[TeamCost]
    top_resources: list[TopResource]
    anomaly_count: int
    resource_count: int
    active_days: int
