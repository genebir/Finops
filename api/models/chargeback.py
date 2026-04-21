"""Chargeback response models."""

from pydantic import BaseModel


class ChargebackTeam(BaseModel):
    team: str
    cost: float
    pct: float
    resource_count: int


class ChargebackItem(BaseModel):
    team: str
    product: str
    env: str
    cost: float
    pct: float


class ChargebackResponse(BaseModel):
    billing_month: str
    available_months: list[str]
    total_cost: float
    by_team: list[ChargebackTeam]
    items: list[ChargebackItem]
