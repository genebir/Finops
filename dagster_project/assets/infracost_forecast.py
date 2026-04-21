"""Infracost Forecast Asset — Infracost CLI 실행 및 dim_forecast 테이블 생성."""


from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from dagster import AssetExecutionContext, asset

from ..core.forecast_provider import ForecastRecord
from ..db_schema import ensure_tables
from ..generators.aws_cur_generator import _TERRAFORM_RESOURCES
from ..resources.duckdb_io import DuckDBResource
from ..resources.infracost_cli import InfracostCliResource


def _parse_forecast_records(breakdown: dict[str, Any]) -> list[ForecastRecord]:
    """Infracost JSON → ForecastRecord 목록 파싱."""
    generated_at = datetime.now(tz=UTC)
    records: list[ForecastRecord] = []

    projects = breakdown.get("projects", [])
    for project in projects:
        resources = (
            project.get("breakdown", {}).get("resources", [])
            or project.get("pastBreakdown", {}).get("resources", [])
        )
        for resource in resources:
            address: str = resource.get("name", "")
            if not address:
                continue

            monthly_raw = resource.get("monthlyCost") or resource.get("monthlyUsageCost") or "0"
            hourly_raw = resource.get("hourlyCost") or "0"

            try:
                monthly = Decimal(str(monthly_raw))
                hourly = Decimal(str(hourly_raw))
            except Exception:
                monthly = Decimal("0")
                hourly = Decimal("0")

            records.append(
                ForecastRecord(
                    resource_address=address,
                    monthly_cost=monthly,
                    hourly_cost=hourly,
                    currency="USD",
                    forecast_generated_at=generated_at,
                )
            )

    return records


def _stub_forecast_records() -> list[ForecastRecord]:
    """Infracost CLI 미설치 시 CUR 생성기의 base_daily_cost × 30으로 mock 예측 생성."""
    generated_at = datetime.now(tz=UTC)
    return [
        ForecastRecord(
            resource_address=res.resource_id,
            monthly_cost=(res.base_daily_cost * Decimal("30")).quantize(Decimal("0.000001")),
            hourly_cost=(res.base_daily_cost / Decimal("24")).quantize(Decimal("0.000001")),
            currency="USD",
            forecast_generated_at=generated_at,
        )
        for res in _TERRAFORM_RESOURCES
    ]


def _write_forecast_rows(conn: Any, rows: list[dict[str, Any]]) -> None:
    import psycopg2.extras

    ensure_tables(conn, "dim_forecast")
    cur = conn.cursor()
    cur.execute("DELETE FROM dim_forecast")
    if not rows:
        cur.close()
        return

    values = [
        (
            r["resource_address"],
            r["monthly_cost"],
            r["hourly_cost"],
            r["currency"],
            r["forecast_generated_at"],
        )
        for r in rows
    ]
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO dim_forecast
            (resource_address, monthly_cost, hourly_cost, currency, forecast_generated_at)
        VALUES %s
        """,
        values,
        page_size=500,
    )
    cur.close()


@asset(
    description=(
        "Infracost CLI로 terraform/sample을 분석하고 월별 예측 비용을 "
        "PostgreSQL dim_forecast 테이블에 저장한다. "
        "CLI 미설치 시 CUR 생성기 base_daily_cost 기반 stub 예측을 사용한다."
    ),
    group_name="forecast",
)
def infracost_forecast(
    context: AssetExecutionContext,
    infracost_cli: InfracostCliResource,
    duckdb_resource: DuckDBResource,
) -> None:
    """Infracost breakdown → dim_forecast 테이블."""
    records: list[ForecastRecord]
    try:
        context.log.info("Running infracost breakdown...")
        breakdown = infracost_cli.breakdown_json()
        records = _parse_forecast_records(breakdown)
        context.log.info(f"Parsed {len(records)} forecast records from infracost")
    except (FileNotFoundError, RuntimeError) as exc:
        context.log.warning(
            f"infracost CLI unavailable ({exc}). "
            "Using stub forecast from CUR generator base costs."
        )
        records = _stub_forecast_records()
        context.log.info(f"Generated {len(records)} stub forecast records")

    rows = [
        {
            "resource_address": r.resource_address,
            "monthly_cost": str(r.monthly_cost),
            "hourly_cost": str(r.hourly_cost),
            "currency": r.currency,
            "forecast_generated_at": r.forecast_generated_at.isoformat(),
        }
        for r in records
    ]

    with duckdb_resource.get_connection() as conn:
        _write_forecast_rows(conn, rows)

    context.log.info(f"Wrote {len(rows)} rows to dim_forecast")
