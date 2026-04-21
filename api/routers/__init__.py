"""FastAPI routers for all API routes."""

from . import (
    anomalies,
    budget,
    burn_rate,
    chargeback,
    cost_allocation,
    cost_explorer,
    data_quality,
    filters,
    forecast,
    inventory,
    overview,
    recommendations,
    settings,
    showback,
    tag_policy,
)

__all__ = [
    "anomalies",
    "budget",
    "burn_rate",
    "chargeback",
    "cost_allocation",
    "cost_explorer",
    "data_quality",
    "filters",
    "forecast",
    "inventory",
    "overview",
    "recommendations",
    "settings",
    "showback",
    "tag_policy",
]
