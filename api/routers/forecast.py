"""GET /api/forecast — Infracost + Prophet predictions vs actuals."""

from fastapi import APIRouter

from ..deps import columns, db_read, f, tables
from ..models import ForecastItem, ForecastResponse

router = APIRouter(tags=["forecast"])


@router.get("/api/forecast", response_model=ForecastResponse)
def get_forecast() -> ForecastResponse:
    with db_read() as db:
        cur = db.cursor()
        _tables = tables(db)
        items: list[ForecastItem] = []

        cur.execute(
            "SELECT resource_id, CAST(SUM(effective_cost) AS DOUBLE PRECISION) "
            "FROM fact_daily_cost GROUP BY resource_id"
        )
        actuals: dict[str, float] = {r[0]: f(r[1]) for r in cur.fetchall()}

        if "dim_forecast" in _tables:
            cur.execute(
                """
                SELECT resource_address,
                       CAST(monthly_cost AS DOUBLE PRECISION),
                       CAST(monthly_cost * 0.85 AS DOUBLE PRECISION),
                       CAST(monthly_cost * 1.15 AS DOUBLE PRECISION)
                FROM dim_forecast ORDER BY monthly_cost DESC
                """
            )
            for r in cur.fetchall():
                actual = actuals.get(r[0])
                forecast_value = f(r[1])
                variance = (
                    round((actual - forecast_value) / forecast_value * 100, 1)
                    if actual and forecast_value
                    else None
                )
                items.append(
                    ForecastItem(
                        resource_id=r[0], monthly_forecast=forecast_value,
                        actual_cost=actual, variance_pct=variance,
                        lower_bound=f(r[2]), upper_bound=f(r[3]),
                        source="infracost",
                    )
                )

        if "dim_prophet_forecast" in _tables:
            cols = columns(db, "dim_prophet_forecast")
            has_bounds = "lower_bound_monthly_cost" in cols
            col_lb = "lower_bound_monthly_cost" if has_bounds else "predicted_monthly_cost * 0.85"
            col_ub = "upper_bound_monthly_cost" if has_bounds else "predicted_monthly_cost * 1.15"
            existing_ids = {i.resource_id for i in items}
            cur.execute(
                f"""
                SELECT resource_id,
                       CAST(predicted_monthly_cost AS DOUBLE PRECISION),
                       CAST({col_lb} AS DOUBLE PRECISION),
                       CAST({col_ub} AS DOUBLE PRECISION)
                FROM dim_prophet_forecast ORDER BY predicted_monthly_cost DESC
                """
            )
            for r in cur.fetchall():
                if r[0] in existing_ids:
                    continue
                actual = actuals.get(r[0])
                forecast_value = f(r[1])
                variance = (
                    round((actual - forecast_value) / forecast_value * 100, 1)
                    if actual and forecast_value
                    else None
                )
                items.append(
                    ForecastItem(
                        resource_id=r[0], monthly_forecast=forecast_value,
                        actual_cost=actual, variance_pct=variance,
                        lower_bound=f(r[2]), upper_bound=f(r[3]),
                        source="prophet",
                    )
                )

        cur.close()

        return ForecastResponse(
            items=items,
            total_forecast=round(sum(i.monthly_forecast for i in items), 2),
            total_actual=round(sum(i.actual_cost or 0 for i in items), 2),
        )
