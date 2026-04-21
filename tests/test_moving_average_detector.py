"""MovingAverageDetector 단위 테스트."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from dagster_project.detectors.moving_average_detector import MovingAverageDetector


def _make_df(costs: list[float], resource_id: str = "res_a") -> pl.DataFrame:
    n = len(costs)
    base = date(2024, 1, 1)
    dates = [date(base.year, base.month, base.day + i).isoformat() for i in range(n)]
    return pl.DataFrame(
        {
            "resource_id": [resource_id] * n,
            "cost_unit_key": ["team_a:product_a:prod"] * n,
            "team": ["team_a"] * n,
            "product": ["product_a"] * n,
            "env": ["prod"] * n,
            "charge_date": dates,
            "effective_cost": costs,
        }
    ).with_columns(pl.col("charge_date").cast(pl.Date))


class TestMovingAverageDetector:
    def test_empty_df_returns_empty(self) -> None:
        df = pl.DataFrame(schema={
            "resource_id": pl.Utf8,
            "cost_unit_key": pl.Utf8,
            "team": pl.Utf8,
            "product": pl.Utf8,
            "env": pl.Utf8,
            "charge_date": pl.Date,
            "effective_cost": pl.Float64,
        })
        detector = MovingAverageDetector()
        assert detector.detect(df) == []

    def test_constant_costs_no_anomaly(self) -> None:
        df = _make_df([100.0] * 14)
        detector = MovingAverageDetector(window_days=7, multiplier_warning=2.0)
        results = detector.detect(df)
        assert results == []

    def test_spike_detected_as_critical(self) -> None:
        costs = [100.0] * 10 + [10000.0]
        df = _make_df(costs)
        detector = MovingAverageDetector(
            window_days=7, multiplier_warning=2.0, multiplier_critical=3.0, min_window=3
        )
        results = detector.detect(df)
        assert len(results) >= 1
        severities = {r.severity for r in results}
        assert "critical" in severities

    def test_moderate_spike_detected_as_warning(self) -> None:
        costs = [100.0, 100.0, 100.0, 100.0, 100.0, 200.0]
        df = _make_df(costs)
        detector = MovingAverageDetector(
            window_days=5, multiplier_warning=1.5, multiplier_critical=10.0, min_window=3
        )
        results = detector.detect(df)
        assert len(results) >= 1
        assert all(r.severity in ("warning", "critical") for r in results)

    def test_too_few_data_points_skipped(self) -> None:
        df = _make_df([100.0, 200.0])
        detector = MovingAverageDetector(min_window=3)
        results = detector.detect(df)
        assert results == []

    def test_result_has_correct_detector_name(self) -> None:
        costs = [100.0] * 10 + [5000.0]
        df = _make_df(costs)
        detector = MovingAverageDetector(window_days=7, min_window=3)
        results = detector.detect(df)
        for r in results:
            assert r.detector_name == "moving_average"

    def test_result_fields_are_correct_types(self) -> None:
        costs = [100.0] * 10 + [5000.0]
        df = _make_df(costs)
        detector = MovingAverageDetector(window_days=7, min_window=3)
        results = detector.detect(df)
        for r in results:
            assert isinstance(r.resource_id, str)
            assert isinstance(r.effective_cost, Decimal)
            assert isinstance(r.mean_cost, Decimal)
            assert isinstance(r.std_cost, Decimal)
            assert isinstance(r.z_score, float)
            assert r.is_anomaly is True

    def test_multiple_resources(self) -> None:
        df_a = _make_df([100.0] * 10 + [9999.0], resource_id="res_a")
        df_b = _make_df([200.0] * 12, resource_id="res_b")
        df = pl.concat([df_a, df_b])
        detector = MovingAverageDetector(window_days=7, min_window=3)
        results = detector.detect(df)
        resource_ids = {r.resource_id for r in results}
        assert "res_a" in resource_ids
        assert "res_b" not in resource_ids

    def test_zero_std_skipped(self) -> None:
        costs = [100.0] * 10
        df = _make_df(costs)
        detector = MovingAverageDetector(window_days=7, min_window=3)
        results = detector.detect(df)
        assert results == []
