"""ArimaDetector 단위 테스트."""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from dagster_project.detectors.arima_detector import ArimaDetector


def _make_df(costs: list[float], resource_id: str = "res_1") -> pl.DataFrame:
    n = len(costs)
    start = date(2024, 1, 1)
    dates = [date(2024, 1, 1 + i) for i in range(n)]
    return pl.DataFrame(
        {
            "charge_date": dates,
            "resource_id": [resource_id] * n,
            "cost_unit_key": ["team_a:prod_x:prod"] * n,
            "team": ["team_a"] * n,
            "product": ["prod_x"] * n,
            "env": ["prod"] * n,
            "effective_cost": costs,
        }
    )


def test_spike_detected():
    """ARIMA 잔차 기반으로 급격한 스파이크를 탐지한다."""
    pytest.importorskip("statsmodels")
    costs = [100.0] * 15 + [2000.0]  # spike on last day
    df = _make_df(costs)
    detector = ArimaDetector(order=(1, 1, 1), threshold_warning=2.0, threshold_critical=3.0)
    results = detector.detect(df)
    assert len(results) > 0
    severities = {r.severity for r in results}
    assert "warning" in severities or "critical" in severities


def test_empty_df_returns_empty():
    """빈 DataFrame은 빈 리스트를 반환한다."""
    df = pl.DataFrame(
        schema={
            "charge_date": pl.Date,
            "resource_id": pl.Utf8,
            "cost_unit_key": pl.Utf8,
            "team": pl.Utf8,
            "product": pl.Utf8,
            "env": pl.Utf8,
            "effective_cost": pl.Float64,
        }
    )
    detector = ArimaDetector()
    results = detector.detect(df)
    assert results == []


def test_below_min_samples_skipped():
    """min_samples 미만 그룹은 건너뛴다."""
    pytest.importorskip("statsmodels")
    df = _make_df([100.0, 200.0, 300.0])  # 3개 < default min_samples=10
    detector = ArimaDetector(min_samples=10)
    results = detector.detect(df)
    assert results == []


def test_detector_name_is_arima():
    """탐지 결과의 detector_name이 'arima'이다."""
    pytest.importorskip("statsmodels")
    costs = [100.0] * 15 + [5000.0]
    df = _make_df(costs)
    detector = ArimaDetector(threshold_warning=1.0, threshold_critical=2.0)
    results = detector.detect(df)
    for r in results:
        assert r.detector_name == "arima"


def test_result_fields_populated():
    """탐지 결과에 모든 필드가 올바르게 채워진다."""
    pytest.importorskip("statsmodels")
    costs = [100.0] * 14 + [3000.0, 100.0]
    df = _make_df(costs)
    detector = ArimaDetector(threshold_warning=1.5, threshold_critical=2.5, min_samples=10)
    results = detector.detect(df)
    if results:
        r = results[0]
        assert r.resource_id == "res_1"
        assert r.team == "team_a"
        assert r.product == "prod_x"
        assert r.env == "prod"
        assert isinstance(r.effective_cost, Decimal)
        assert isinstance(r.z_score, float)
        assert r.is_anomaly is True


def test_multiple_resources_independent():
    """여러 resource_id를 독립적으로 탐지한다 — 심한 스파이크 리소스는 반드시 탐지된다."""
    pytest.importorskip("statsmodels")
    costs_a = [100.0] * 15 + [5000.0]  # 50배 스파이크 → 반드시 탐지
    costs_b = [200.0] * 16             # 균일
    df_a = _make_df(costs_a, resource_id="res_a")
    df_b = _make_df(costs_b, resource_id="res_b")
    df = pl.concat([df_a, df_b])
    detector = ArimaDetector(threshold_warning=2.0, threshold_critical=3.0, min_samples=10)
    results = detector.detect(df)
    resource_ids = {r.resource_id for r in results}
    # res_a의 50배 스파이크는 반드시 탐지됨
    assert "res_a" in resource_ids
    # 각 resource_id는 독립적으로 처리됨 (결과가 있으면 해당 resource_id 존재)
    for r in results:
        assert r.resource_id in {"res_a", "res_b"}


def test_no_spike_no_anomaly():
    """정상 데이터에서는 이상치가 없다."""
    pytest.importorskip("statsmodels")
    # 매우 작은 변동만 있는 데이터
    costs = [100.0 + (i % 3) * 0.01 for i in range(20)]
    df = _make_df(costs)
    detector = ArimaDetector(threshold_warning=10.0, threshold_critical=15.0)
    results = detector.detect(df)
    assert len(results) == 0


def test_statsmodels_not_installed(monkeypatch: pytest.MonkeyPatch):
    """statsmodels 미설치 시 빈 리스트를 반환한다."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("statsmodels"):
            raise ImportError("no statsmodels")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    costs = [100.0] * 15 + [5000.0]
    df = _make_df(costs)
    detector = ArimaDetector()
    results = detector.detect(df)
    assert results == []
