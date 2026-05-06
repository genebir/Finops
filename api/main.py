"""FinOps Platform API — FastAPI entry point.

The app is split into:
- api/deps.py        — DB connection helpers (read-only per-request + write with retry)
- api/models/*       — Pydantic request/response models, one file per domain
- api/routers/*      — Endpoints grouped by domain, each with its own APIRouter

Adding a new endpoint:
1. Add/extend models in api/models/<domain>.py
2. Create or extend api/routers/<domain>.py with a router and endpoint
3. Register the router below (app.include_router(...))
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .middleware import RequestContextMiddleware
from .routers import (
    alert_rules,
    alerts,
    anomalies,
    anomaly_timeline,
    cloud_config,
    budget_forecast,
    cloud_compare,
    env_breakdown,
    env_detail,
    cost_heatmap,
    cost_risk,
    leaderboard,
    pipeline,
    resource_detail,
    savings,
    search,
    service_breakdown,
    service_detail,
    budget,
    burn_rate,
    chargeback,
    cost_allocation,
    cost_explorer,
    cost_trend,
    data_quality,
    filters,
    forecast,
    inventory,
    ops,
    overview,
    recommendations,
    settings,
    showback,
    tag_compliance,
    tag_policy,
    team_detail,
)

app = FastAPI(
    title="FinOps Platform API",
    version="0.2.0",
    description="Cost Intelligence API — backs the Next.js dashboard.",
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["x-request-id"],
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Lightweight liveness probe — returns ok if the process is responding."""
    return {"status": "ok"}


app.include_router(overview.router)
app.include_router(anomalies.router)
app.include_router(forecast.router)
app.include_router(budget.router)
app.include_router(cost_explorer.router)
app.include_router(recommendations.router)
app.include_router(chargeback.router)
app.include_router(settings.router)
app.include_router(filters.router)
app.include_router(ops.router)
app.include_router(data_quality.router)
app.include_router(burn_rate.router)
app.include_router(inventory.router)
app.include_router(tag_policy.router)
app.include_router(cost_allocation.router)
app.include_router(showback.router)
app.include_router(cost_trend.router)
app.include_router(alerts.router)
app.include_router(cloud_compare.router)
app.include_router(savings.router)
app.include_router(cost_heatmap.router)
app.include_router(cost_risk.router)
app.include_router(resource_detail.router)
app.include_router(leaderboard.router)
app.include_router(service_breakdown.router)
app.include_router(service_detail.router)
app.include_router(budget_forecast.router)
app.include_router(env_breakdown.router)
app.include_router(env_detail.router)
app.include_router(tag_compliance.router)
app.include_router(anomaly_timeline.router)
app.include_router(cloud_config.router)
app.include_router(team_detail.router)
app.include_router(pipeline.router)
app.include_router(search.router)
app.include_router(alert_rules.router)
