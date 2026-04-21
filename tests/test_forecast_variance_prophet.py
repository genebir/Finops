"""forecast_variance_prophet asset 로직 테스트."""

from decimal import Decimal

import pytest

from dagster_project.core.forecast_provider import ForecastRecord


def test_forecast_record_has_confidence_bounds() -> None:
    """ForecastRecord에 lower/upper bound 필드가 있다."""
    from datetime import UTC, datetime

    rec = ForecastRecord(
        resource_address="res_1",
        monthly_cost=Decimal("100.0"),
        hourly_cost=Decimal("0.14"),
        currency="USD",
        forecast_generated_at=datetime(2024, 1, 1, tzinfo=UTC),
        lower_bound_monthly_cost=Decimal("80.0"),
        upper_bound_monthly_cost=Decimal("120.0"),
    )
    assert rec.lower_bound_monthly_cost == Decimal("80.0")
    assert rec.upper_bound_monthly_cost == Decimal("120.0")


def test_forecast_record_default_bounds() -> None:
    """lower/upper 미지정 시 기본값 0."""
    from datetime import UTC, datetime

    rec = ForecastRecord(
        resource_address="res_1",
        monthly_cost=Decimal("50.0"),
        hourly_cost=Decimal("0.07"),
        currency="USD",
        forecast_generated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    assert rec.lower_bound_monthly_cost == Decimal("0")
    assert rec.upper_bound_monthly_cost == Decimal("0")


def test_status_logic_within_bounds() -> None:
    """실제 비용이 lower~upper 내에 있으면 within_bounds."""
    actual = 95.0
    lower = 80.0
    upper = 120.0
    status = _compute_status(actual, lower, upper, has_actual=True)
    assert status == "within_bounds"


def test_status_logic_above_upper() -> None:
    actual = 150.0
    lower = 80.0
    upper = 120.0
    status = _compute_status(actual, lower, upper, has_actual=True)
    assert status == "above_upper"


def test_status_logic_below_lower() -> None:
    actual = 50.0
    lower = 80.0
    upper = 120.0
    status = _compute_status(actual, lower, upper, has_actual=True)
    assert status == "below_lower"


def test_status_logic_no_actual() -> None:
    status = _compute_status(0.0, 80.0, 120.0, has_actual=False)
    assert status == "no_actual"


def _compute_status(actual: float, lower: float, upper: float, *, has_actual: bool) -> str:
    """forecast_variance_prophet의 status 계산 로직 재현."""
    if not has_actual:
        return "no_actual"
    if actual > upper:
        return "above_upper"
    if actual < lower:
        return "below_lower"
    return "within_bounds"


def test_anomaly_result_has_detector_name() -> None:
    """AnomalyResult에 detector_name 필드가 있다."""
    from datetime import date
    from dagster_project.core.anomaly_detector import AnomalyResult

    result = AnomalyResult(
        resource_id="r1",
        cost_unit_key="a:b:c",
        team="a",
        product="b",
        env="c",
        charge_date=date(2024, 1, 1),
        effective_cost=Decimal("10.0"),
        mean_cost=Decimal("5.0"),
        std_cost=Decimal("1.0"),
        z_score=5.0,
        is_anomaly=True,
        severity="critical",
        detector_name="isolation_forest",
    )
    assert result.detector_name == "isolation_forest"


def test_anomaly_result_default_detector_name() -> None:
    """detector_name 기본값은 zscore."""
    from datetime import date
    from dagster_project.core.anomaly_detector import AnomalyResult

    result = AnomalyResult(
        resource_id="r1",
        cost_unit_key="a:b:c",
        team="a",
        product="b",
        env="c",
        charge_date=date(2024, 1, 1),
        effective_cost=Decimal("10.0"),
        mean_cost=Decimal("5.0"),
        std_cost=Decimal("1.0"),
        z_score=5.0,
        is_anomaly=True,
        severity="critical",
    )
    assert result.detector_name == "zscore"
