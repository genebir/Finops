"""Cost Explorer response models."""

from pydantic import BaseModel


class DailyCost(BaseModel):
    charge_date: str
    cost: float


class ServiceCost(BaseModel):
    service_name: str
    cost: float
    pct: float


class ProviderCost(BaseModel):
    provider: str
    cost: float
    pct: float


class CostExplorerResponse(BaseModel):
    daily: list[DailyCost]
    by_service: list[ServiceCost]
    by_provider: list[ProviderCost]
    total: float
    avg_daily: float
