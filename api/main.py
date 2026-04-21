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

from .routers import (
    anomalies,
    budget,
    chargeback,
    cost_explorer,
    filters,
    forecast,
    overview,
    recommendations,
    settings,
)

app = FastAPI(
    title="FinOps Platform API",
    version="0.2.0",
    description="Cost Intelligence API — backs the Next.js dashboard.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
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
