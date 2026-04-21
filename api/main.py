"""FinOps Platform API"""

import os
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, Generator

import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

_DB_PATH = os.getenv("DUCKDB_PATH", "data/marts.duckdb")

app = FastAPI(title="FinOps Platform API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@contextmanager
def _db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Open a short-lived read-only connection per request so Dagster can write."""
    if not os.path.exists(_DB_PATH):
        raise HTTPException(status_code=503, detail=f"Database not found: {_DB_PATH}")
    conn = duckdb.connect(_DB_PATH, read_only=True)
    try:
        yield conn
    finally:
        conn.close()


def _f(v: Any) -> float:
    if v is None:
        return 0.0
    return float(Decimal(str(v)))


def _tables(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {r[0] for r in conn.execute("SHOW TABLES").fetchall()}


# ── Models ────────────────────────────────────────────────────────────────────

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


class BudgetItem(BaseModel):
    team: str
    env: str
    budget_amount: float
    actual_cost: float
    used_pct: float
    status: str  # "ok" | "warning" | "over"


class BudgetResponse(BaseModel):
    items: list[BudgetItem]
    total_budget: float
    total_actual: float


class DailyCost(BaseModel):
    charge_date: str
    cost: float


class ServiceCost(BaseModel):
    service_name: str
    cost: float
    pct: float


class CostExplorerResponse(BaseModel):
    daily: list[DailyCost]
    by_service: list[ServiceCost]
    total: float
    avg_daily: float


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
    total_cost: float
    by_team: list[ChargebackTeam]
    items: list[ChargebackItem]


class SettingItem(BaseModel):
    key: str
    value: str


class SettingsResponse(BaseModel):
    items: list[SettingItem]


# ── /api/overview ─────────────────────────────────────────────────────────────

@app.get("/api/overview", response_model=OverviewResponse)
def get_overview() -> OverviewResponse:
    with _db() as db:
        summary = db.execute("""
            SELECT
                MIN(charge_date)::VARCHAR            AS period_start,
                MAX(charge_date)::VARCHAR            AS period_end,
                CAST(SUM(effective_cost) AS DOUBLE)  AS total_cost,
                COUNT(DISTINCT resource_id)          AS resource_count,
                COUNT(DISTINCT charge_date)          AS active_days
            FROM fact_daily_cost
        """).fetchone()

        if not summary or summary[2] is None:
            raise HTTPException(status_code=404, detail="No cost data found")

        period_start, period_end, total_cost, resource_count, active_days = summary

        team_rows = db.execute("""
            SELECT team, CAST(SUM(effective_cost) AS DOUBLE) AS cost
            FROM fact_daily_cost
            GROUP BY team ORDER BY cost DESC
        """).fetchall()

        total = _f(total_cost) or 1.0
        cost_by_team = [
            TeamCost(team=r[0], cost=_f(r[1]), pct=round(_f(r[1]) / total * 100, 1))
            for r in team_rows
        ]

        resource_rows = db.execute("""
            SELECT resource_id, resource_name, service_name, region_id,
                   team, product, env,
                   CAST(SUM(effective_cost) AS DOUBLE) AS cost,
                   COUNT(DISTINCT charge_date) AS active_days
            FROM fact_daily_cost
            GROUP BY resource_id, resource_name, service_name, region_id, team, product, env
            ORDER BY cost DESC LIMIT 10
        """).fetchall()

        top_resources = [
            TopResource(
                resource_id=r[0], resource_name=r[1], service_name=r[2],
                region_id=r[3], team=r[4], product=r[5], env=r[6],
                cost=_f(r[7]), active_days=r[8],
            )
            for r in resource_rows
        ]

        anomaly_count = 0
        if "anomaly_scores" in _tables(db):
            row = db.execute("SELECT COUNT(*) FROM anomaly_scores WHERE is_anomaly = true").fetchone()
            anomaly_count = row[0] if row else 0

        return OverviewResponse(
            period_start=period_start, period_end=period_end,
            total_cost=round(_f(total_cost), 2),
            cost_by_team=cost_by_team, top_resources=top_resources,
            anomaly_count=anomaly_count, resource_count=resource_count,
            active_days=active_days,
        )


# ── /api/anomalies ────────────────────────────────────────────────────────────

@app.get("/api/anomalies", response_model=AnomaliesResponse)
def get_anomalies(
    severity: str | None = Query(None, description="critical | warning"),
    limit: int = Query(100, le=500),
) -> AnomaliesResponse:
    with _db() as db:
        if "anomaly_scores" not in _tables(db):
            return AnomaliesResponse(items=[], total=0, critical=0, warning=0)

        where = "WHERE is_anomaly = true"
        if severity:
            where += f" AND severity = '{severity}'"

        has_detector = any(
            col[0] == "detector_name"
            for col in db.execute("DESCRIBE anomaly_scores").fetchall()
        )
        detector_col = "detector_name" if has_detector else "'zscore' AS detector_name"

        rows = db.execute(f"""
            SELECT resource_id, cost_unit_key, team, product, env,
                   charge_date::VARCHAR, CAST(effective_cost AS DOUBLE),
                   CAST(z_score AS DOUBLE), severity, {detector_col}
            FROM anomaly_scores
            {where}
            ORDER BY charge_date DESC, z_score DESC
            LIMIT {limit}
        """).fetchall()

        counts = db.execute("""
            SELECT severity, COUNT(*) FROM anomaly_scores
            WHERE is_anomaly = true GROUP BY severity
        """).fetchall()
        count_map = {r[0]: r[1] for r in counts}

        items = [
            AnomalyItem(
                resource_id=r[0], cost_unit_key=r[1], team=r[2], product=r[3],
                env=r[4], charge_date=r[5], effective_cost=_f(r[6]),
                z_score=_f(r[7]), severity=r[8], detector_name=r[9],
            )
            for r in rows
        ]

        return AnomaliesResponse(
            items=items,
            total=count_map.get("critical", 0) + count_map.get("warning", 0),
            critical=count_map.get("critical", 0),
            warning=count_map.get("warning", 0),
        )


# ── /api/forecast ─────────────────────────────────────────────────────────────

@app.get("/api/forecast", response_model=ForecastResponse)
def get_forecast() -> ForecastResponse:
    with _db() as db:
        tables = _tables(db)
        items: list[ForecastItem] = []

        actuals: dict[str, float] = {}
        for r in db.execute("""
            SELECT resource_id, CAST(SUM(effective_cost) AS DOUBLE)
            FROM fact_daily_cost GROUP BY resource_id
        """).fetchall():
            actuals[r[0]] = _f(r[1])

        if "dim_forecast" in tables:
            for r in db.execute("""
                SELECT resource_address,
                       CAST(monthly_cost AS DOUBLE),
                       CAST(monthly_cost * 0.85 AS DOUBLE),
                       CAST(monthly_cost * 1.15 AS DOUBLE)
                FROM dim_forecast ORDER BY monthly_cost DESC
            """).fetchall():
                actual = actuals.get(r[0])
                variance = round((actual - _f(r[1])) / _f(r[1]) * 100, 1) if actual and _f(r[1]) else None
                items.append(ForecastItem(
                    resource_id=r[0], monthly_forecast=_f(r[1]),
                    actual_cost=actual, variance_pct=variance,
                    lower_bound=_f(r[2]), upper_bound=_f(r[3]),
                    source="infracost",
                ))

        if "dim_prophet_forecast" in tables:
            has_bounds = any(
                col[0] in ("lower_bound_monthly_cost", "lower_bound")
                for col in db.execute("DESCRIBE dim_prophet_forecast").fetchall()
            )
            col_lb = "lower_bound_monthly_cost" if has_bounds else "predicted_monthly_cost * 0.85"
            col_ub = "upper_bound_monthly_cost" if has_bounds else "predicted_monthly_cost * 1.15"
            existing_ids = {i.resource_id for i in items}
            for r in db.execute(f"""
                SELECT resource_id,
                       CAST(predicted_monthly_cost AS DOUBLE),
                       CAST({col_lb} AS DOUBLE),
                       CAST({col_ub} AS DOUBLE)
                FROM dim_prophet_forecast ORDER BY predicted_monthly_cost DESC
            """).fetchall():
                if r[0] in existing_ids:
                    continue
                actual = actuals.get(r[0])
                variance = round((actual - _f(r[1])) / _f(r[1]) * 100, 1) if actual and _f(r[1]) else None
                items.append(ForecastItem(
                    resource_id=r[0], monthly_forecast=_f(r[1]),
                    actual_cost=actual, variance_pct=variance,
                    lower_bound=_f(r[2]), upper_bound=_f(r[3]),
                    source="prophet",
                ))

        return ForecastResponse(
            items=items,
            total_forecast=round(sum(i.monthly_forecast for i in items), 2),
            total_actual=round(sum(i.actual_cost or 0 for i in items), 2),
        )


# ── /api/budget ───────────────────────────────────────────────────────────────

@app.get("/api/budget", response_model=BudgetResponse)
def get_budget() -> BudgetResponse:
    with _db() as db:
        tables = _tables(db)
        if "dim_budget_status" not in tables:
            team_rows = db.execute("""
                SELECT team, env, CAST(SUM(effective_cost) AS DOUBLE)
                FROM fact_daily_cost GROUP BY team, env ORDER BY 3 DESC
            """).fetchall()
            items = [
                BudgetItem(
                    team=r[0], env=r[1], budget_amount=0.0,
                    actual_cost=_f(r[2]), used_pct=0.0, status="unknown",
                )
                for r in team_rows
            ]
            return BudgetResponse(items=items, total_budget=0.0,
                                  total_actual=sum(i.actual_cost for i in items))

        cols = {c[0] for c in db.execute("DESCRIBE dim_budget_status").fetchall()}
        status_col = "status" if "status" in cols else (
            "CASE WHEN used_pct >= 100 THEN 'over' WHEN used_pct >= 80 THEN 'warning' ELSE 'ok' END"
        )

        rows = db.execute(f"""
            SELECT team, env,
                   CAST(budget_amount AS DOUBLE),
                   CAST(actual_cost AS DOUBLE),
                   CAST(used_pct AS DOUBLE),
                   {status_col}
            FROM dim_budget_status
            ORDER BY used_pct DESC
        """).fetchall()

        items = [
            BudgetItem(
                team=r[0], env=r[1], budget_amount=_f(r[2]),
                actual_cost=_f(r[3]), used_pct=_f(r[4]), status=r[5],
            )
            for r in rows
        ]

        return BudgetResponse(
            items=items,
            total_budget=sum(i.budget_amount for i in items),
            total_actual=sum(i.actual_cost for i in items),
        )


# ── /api/cost-explorer ────────────────────────────────────────────────────────

@app.get("/api/cost-explorer", response_model=CostExplorerResponse)
def get_cost_explorer(
    team: str | None = Query(None),
    env: str | None = Query(None),
    service: str | None = Query(None),
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None, description="YYYY-MM-DD"),
) -> CostExplorerResponse:
    with _db() as db:
        conditions = []
        if team:
            conditions.append(f"team = '{team}'")
        if env:
            conditions.append(f"env = '{env}'")
        if service:
            conditions.append(f"service_name = '{service}'")
        if start:
            conditions.append(f"charge_date >= DATE '{start}'")
        if end:
            conditions.append(f"charge_date <= DATE '{end}'")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        daily_rows = db.execute(f"""
            SELECT charge_date::VARCHAR, CAST(SUM(effective_cost) AS DOUBLE)
            FROM fact_daily_cost {where}
            GROUP BY charge_date ORDER BY charge_date
        """).fetchall()

        service_rows = db.execute(f"""
            SELECT service_name, CAST(SUM(effective_cost) AS DOUBLE) AS cost
            FROM fact_daily_cost {where}
            GROUP BY service_name ORDER BY cost DESC
        """).fetchall()

        total = sum(_f(r[1]) for r in daily_rows) or 1.0
        avg_daily = total / len(daily_rows) if daily_rows else 0.0

        by_service = [
            ServiceCost(
                service_name=r[0] or "Unknown",
                cost=_f(r[1]),
                pct=round(_f(r[1]) / total * 100, 1),
            )
            for r in service_rows
        ]

        return CostExplorerResponse(
            daily=[DailyCost(charge_date=r[0], cost=_f(r[1])) for r in daily_rows],
            by_service=by_service,
            total=round(total, 2),
            avg_daily=round(avg_daily, 2),
        )


# ── /api/recommendations ──────────────────────────────────────────────────────

@app.get("/api/recommendations", response_model=RecommendationsResponse)
def get_recommendations() -> RecommendationsResponse:
    with _db() as db:
        if "dim_cost_recommendations" not in _tables(db):
            return RecommendationsResponse(items=[], total_potential_savings=0.0)

        cols = {c[0] for c in db.execute("DESCRIBE dim_cost_recommendations").fetchall()}
        savings_col = "potential_savings" if "potential_savings" in cols else "0.0"
        severity_col = "severity" if "severity" in cols else "'info'"
        desc_col = "description" if "description" in cols else "rule_type"

        rows = db.execute(f"""
            SELECT rule_type, resource_id, team, env,
                   {desc_col}, CAST({savings_col} AS DOUBLE), {severity_col}
            FROM dim_cost_recommendations
            ORDER BY {savings_col} DESC
        """).fetchall()

        items = [
            RecommendationItem(
                rule_type=r[0], resource_id=r[1], team=r[2], env=r[3],
                description=r[4], potential_savings=_f(r[5]), severity=r[6],
            )
            for r in rows
        ]

        return RecommendationsResponse(
            items=items,
            total_potential_savings=round(sum(i.potential_savings for i in items), 2),
        )


# ── /api/chargeback ───────────────────────────────────────────────────────────

@app.get("/api/chargeback", response_model=ChargebackResponse)
def get_chargeback() -> ChargebackResponse:
    with _db() as db:
        tables = _tables(db)

        if "dim_chargeback" in tables:
            month_row = db.execute(
                "SELECT MAX(billing_month)::VARCHAR FROM dim_chargeback"
            ).fetchone()
            billing_month = month_row[0] if month_row and month_row[0] else "unknown"
            rows = db.execute("""
                SELECT team, product, env, CAST(SUM(allocated_cost) AS DOUBLE) AS cost
                FROM dim_chargeback
                GROUP BY team, product, env ORDER BY cost DESC
            """).fetchall()
        else:
            month_row = db.execute(
                "SELECT strftime(MAX(charge_date), '%Y-%m') FROM fact_daily_cost"
            ).fetchone()
            billing_month = month_row[0] if month_row and month_row[0] else "unknown"
            rows = db.execute("""
                SELECT team, product, env, CAST(SUM(effective_cost) AS DOUBLE) AS cost
                FROM fact_daily_cost
                GROUP BY team, product, env ORDER BY cost DESC
            """).fetchall()

        total = sum(_f(r[3]) for r in rows) or 1.0

        items = [
            ChargebackItem(
                team=r[0], product=r[1], env=r[2],
                cost=_f(r[3]), pct=round(_f(r[3]) / total * 100, 1),
            )
            for r in rows
        ]

        team_totals: dict[str, dict[str, float]] = {}
        for item in items:
            t = item.team
            if t not in team_totals:
                team_totals[t] = {"cost": 0.0, "count": 0.0}
            team_totals[t]["cost"] += item.cost
            team_totals[t]["count"] += 1

        by_team = [
            ChargebackTeam(
                team=t,
                cost=round(v["cost"], 2),
                pct=round(v["cost"] / total * 100, 1),
                resource_count=int(v["count"]),
            )
            for t, v in sorted(team_totals.items(), key=lambda x: -x[1]["cost"])
        ]

        return ChargebackResponse(
            billing_month=billing_month,
            total_cost=round(total, 2),
            by_team=by_team,
            items=items,
        )


# ── /api/settings ─────────────────────────────────────────────────────────────

@app.get("/api/settings", response_model=SettingsResponse)
def get_settings() -> SettingsResponse:
    with _db() as db:
        if "platform_settings" not in _tables(db):
            return SettingsResponse(items=[])
        rows = db.execute("SELECT key, value FROM platform_settings ORDER BY key").fetchall()
        return SettingsResponse(items=[SettingItem(key=r[0], value=str(r[1])) for r in rows])
