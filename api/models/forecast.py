"""Forecast response models."""

from pydantic import BaseModel


class ForecastItem(BaseModel):
    resource_id: str
    monthly_forecast: float
    actual_cost: float | None
    variance_pct: float | None
    lower_bound: float
    upper_bound: float
    source: str  # "infracost" | "prophet"


class ForecastResponse(BaseModel):
    items: list[ForecastItem]
    total_forecast: float
    total_actual: float
