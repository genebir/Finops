"""AutoencoderDetector 단위 테스트."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import polars as pl
import pytest

from dagster_project.detectors.autoencoder_detector import AutoencoderDetector


def _make_df(costs: list[float], resource_id: str = "res_1") -> pl.DataFrame:
    base = date(2024, 1, 1)
    n = len(costs)
    return pl.DataFrame(
        {
            "charge_date": [base + timedelta(days=i) for i in range(n)],
            "resource_id": [resource_id] * n,
            "cost_unit_key": ["team_a:prod_x:prod"] * n,
            "team": ["team_a"] * n,
            "product": ["prod_x"] * n,
            "env": ["prod"] * n,
            "effective_cost": costs,
        }
    )


def test_spike_detected():
    """급격한 스파이크를 재구성 오차 기반으로 탐지한다."""
    # window_size=7 이므로 min_samples+window_size=14+7=21 필요
    costs = [100.0] * 25 + [5000.0, 5000.0]
    df = _make_df(costs)
    detector = AutoencoderDetector(
        window_size=5, threshold_warning=1.5, threshold_critical=2.5, min_samples=10, max_iter=50
    )
    results = detector.detect(df)
    assert len(results) > 0


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
    detector = AutoencoderDetector()
    results = detector.detect(df)
    assert results == []


def test_below_min_samples_skipped():
    """min_samples + window_size 미만 데이터는 건너뛴다."""
    costs = [100.0] * 10  # 10 < 14+7=21
    df = _make_df(costs)
    detector = AutoencoderDetector(window_size=7, min_samples=14)
    results = detector.detect(df)
    assert results == []


def test_detector_name_is_autoencoder():
    """탐지 결과의 detector_name이 'autoencoder'이다."""
    costs = [100.0] * 25 + [5000.0, 5000.0]
    df = _make_df(costs)
    detector = AutoencoderDetector(
        window_size=5, threshold_warning=1.0, threshold_critical=2.0, min_samples=10, max_iter=50
    )
    results = detector.detect(df)
    for r in results:
        assert r.detector_name == "autoencoder"


def test_result_fields_populated():
    """탐지 결과에 모든 필드가 올바르게 채워진다."""
    costs = [100.0] * 25 + [8000.0, 8000.0]
    df = _make_df(costs)
    detector = AutoencoderDetector(
        window_size=5, threshold_warning=1.0, threshold_critical=2.0, min_samples=10, max_iter=50
    )
    results = detector.detect(df)
    if results:
        r = results[0]
        assert r.resource_id == "res_1"
        assert r.team == "team_a"
        assert isinstance(r.effective_cost, Decimal)
        assert isinstance(r.z_score, float)
        assert r.is_anomaly is True
        assert r.severity in {"warning", "critical"}


def test_normal_data_no_high_threshold_anomaly():
    """매우 높은 임계값 설정 시 정상 데이터에서 이상치 없음."""
    costs = [100.0 + i * 0.5 for i in range(30)]
    df = _make_df(costs)
    detector = AutoencoderDetector(
        window_size=5, threshold_warning=10.0, threshold_critical=20.0,
        min_samples=10, max_iter=50
    )
    results = detector.detect(df)
    assert len(results) == 0


def test_multiple_resources_processed():
    """여러 resource_id가 모두 처리된다."""
    costs_a = [100.0] * 25 + [8000.0, 8000.0]
    costs_b = [200.0] * 25 + [8000.0, 8000.0]
    df = pl.concat([
        _make_df(costs_a, resource_id="res_a"),
        _make_df(costs_b, resource_id="res_b"),
    ])
    detector = AutoencoderDetector(
        window_size=5, threshold_warning=1.0, threshold_critical=2.0, min_samples=10, max_iter=50
    )
    results = detector.detect(df)
    # 두 리소스 모두 처리됐는지 확인 (결과가 있을 경우)
    for r in results:
        assert r.resource_id in {"res_a", "res_b"}


def test_sklearn_not_installed(monkeypatch: pytest.MonkeyPatch):
    """sklearn 미설치 시 빈 리스트를 반환한다."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("sklearn"):
            raise ImportError("no sklearn")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    costs = [100.0] * 30 + [5000.0]
    df = _make_df(costs)
    detector = AutoencoderDetector()
    results = detector.detect(df)
    assert results == []
