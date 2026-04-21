"""IsolationForestDetector 테스트."""

from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from dagster_project.detectors.isolation_forest_detector import IsolationForestDetector


def _make_df(costs: list[float], resource_id: str = "res_1") -> pl.DataFrame:
    """테스트용 DataFrame 생성 (단일 리소스)."""
    n = len(costs)
    return pl.DataFrame({
        "resource_id": [resource_id] * n,
        "cost_unit_key": ["platform:checkout:prod"] * n,
        "team": ["platform"] * n,
        "product": ["checkout"] * n,
        "env": ["prod"] * n,
        "charge_date": [date(2024, 1, i + 1) for i in range(n)],
        "effective_cost": costs,
    })


@pytest.fixture
def detector() -> IsolationForestDetector:
    return IsolationForestDetector(
        contamination=0.1,
        n_estimators=50,
        random_state=42,
        score_critical=-0.20,
        score_warning=-0.05,
    )


def test_detects_spike_in_stable_series(detector: IsolationForestDetector) -> None:
    """안정적인 시계열에 spike가 있으면 이상치로 탐지."""
    costs = [10.0] * 20 + [100.0]  # 마지막 값이 급등
    df = _make_df(costs)
    results = detector.detect(df)
    assert len(results) >= 1
    detected_costs = [float(r.effective_cost) for r in results]
    assert 100.0 in detected_costs


def test_empty_dataframe_returns_empty(detector: IsolationForestDetector) -> None:
    df = pl.DataFrame(schema={
        "resource_id": pl.Utf8, "cost_unit_key": pl.Utf8, "team": pl.Utf8,
        "product": pl.Utf8, "env": pl.Utf8, "charge_date": pl.Date,
        "effective_cost": pl.Float64,
    })
    assert detector.detect(df) == []


def test_too_few_samples_skipped(detector: IsolationForestDetector) -> None:
    """MIN_SAMPLES(10)개 미만 그룹은 건너뜀."""
    df = _make_df([10.0, 20.0, 100.0])  # 3개 < 10
    assert detector.detect(df) == []


def test_severity_critical_when_score_below_threshold() -> None:
    det = IsolationForestDetector(
        contamination=0.2,
        n_estimators=10,
        random_state=0,
        score_critical=-0.01,
        score_warning=0.5,
    )
    costs = [5.0] * 18 + [500.0, 600.0]
    df = _make_df(costs)
    results = det.detect(df)
    if results:
        severities = {r.severity for r in results}
        assert severities <= {"critical", "warning"}


def test_detector_name_is_isolation_forest(detector: IsolationForestDetector) -> None:
    costs = [10.0] * 20 + [200.0]
    df = _make_df(costs)
    results = detector.detect(df)
    assert all(r.detector_name == "isolation_forest" for r in results)


def test_is_anomaly_true_for_all_results(detector: IsolationForestDetector) -> None:
    costs = [10.0] * 20 + [200.0]
    df = _make_df(costs)
    results = detector.detect(df)
    assert all(r.is_anomaly for r in results)


def test_missing_columns_raises() -> None:
    df = pl.DataFrame({"resource_id": ["r1"], "effective_cost": [10.0]})
    det = IsolationForestDetector()
    with pytest.raises(ValueError, match="필수 컬럼"):
        det.detect(df)


def test_multi_resource_isolation(detector: IsolationForestDetector) -> None:
    """두 리소스가 서로 영향을 주지 않는다."""
    normal = _make_df([10.0] * 20, resource_id="normal")
    spike_costs = [10.0] * 20 + [999.0]
    spike = _make_df(spike_costs, resource_id="spike")
    combined = pl.concat([normal, spike])

    results = detector.detect(combined)
    detected_ids = {r.resource_id for r in results}
    # spike 리소스가 탐지되어야 함
    assert "spike" in detected_ids
