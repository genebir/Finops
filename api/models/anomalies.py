"""Anomaly response models."""

from pydantic import BaseModel


class AnomalyItem(BaseModel):
    resource_id: str
    cost_unit_key: str
    team: str
    product: str
    env: str
    charge_date: str
    effective_cost: float
    z_score: float
    severity: str
    detector_name: str


class AnomaliesResponse(BaseModel):
    items: list[AnomalyItem]
    total: int
    critical: int
    warning: int
