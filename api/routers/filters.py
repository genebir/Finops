"""GET /api/filters — dropdown options for the dashboard."""

from fastapi import APIRouter

from ..deps import columns, db_read, tables
from ..models import FiltersResponse

router = APIRouter(tags=["filters"])


@router.get("/api/filters", response_model=FiltersResponse)
def get_filters() -> FiltersResponse:
    """Return all distinct values needed to populate dashboard dropdowns.

    Single round-trip so the frontend doesn't need to fetch /api/overview
    just to collect the list of teams.
    """
    with db_read() as db:
        if "fact_daily_cost" not in tables(db):
            return FiltersResponse(
                teams=[], envs=[], providers=[], services=[],
                billing_months=[], date_min=None, date_max=None,
            )

        cur = db.cursor()
        fact_cols = columns(db, "fact_daily_cost")
        provider_expr = "provider" if "provider" in fact_cols else "'aws'"

        cur.execute(
            "SELECT DISTINCT team FROM fact_daily_cost WHERE team IS NOT NULL ORDER BY team"
        )
        teams = [r[0] for r in cur.fetchall() if r[0]]

        cur.execute(
            "SELECT DISTINCT env FROM fact_daily_cost WHERE env IS NOT NULL ORDER BY env"
        )
        envs = [r[0] for r in cur.fetchall() if r[0]]

        cur.execute(
            f"SELECT DISTINCT {provider_expr} AS p FROM fact_daily_cost ORDER BY p"
        )
        providers = [r[0] for r in cur.fetchall() if r[0]]

        cur.execute(
            "SELECT DISTINCT service_name FROM fact_daily_cost "
            "WHERE service_name IS NOT NULL ORDER BY service_name"
        )
        services = [r[0] for r in cur.fetchall() if r[0]]

        cur.execute(
            "SELECT DISTINCT to_char(charge_date, 'YYYY-MM') AS m "
            "FROM fact_daily_cost ORDER BY m DESC"
        )
        billing_months = [r[0] for r in cur.fetchall() if r[0]]

        cur.execute(
            "SELECT MIN(charge_date)::TEXT, MAX(charge_date)::TEXT FROM fact_daily_cost"
        )
        date_range = cur.fetchone()
        date_min = date_range[0] if date_range and date_range[0] else None
        date_max = date_range[1] if date_range and date_range[1] else None

        cur.close()

        return FiltersResponse(
            teams=teams, envs=envs, providers=providers, services=services,
            billing_months=billing_months, date_min=date_min, date_max=date_max,
        )
