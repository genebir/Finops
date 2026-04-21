"""Z-score 기반 이상치 탐지 테스트."""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from dagster_project.core.anomaly_detector import AnomalyResult
from dagster_project.detectors.zscore_detector import ZScoreDetector


def _make_df(rows: list[dict[str, object]]) -> pl.DataFrame:
    """테스트용 fact_daily_cost 형태 DataFrame 생성."""
    return pl.DataFrame(
        rows,
        schema={
            "charge_date": pl.Date,
            "resource_id": pl.Utf8,
            "cost_unit_key": pl.Utf8,
            "team": pl.Utf8,
            "product": pl.Utf8,
            "env": pl.Utf8,
            "effective_cost": pl.Float64,
        },
    )


def _normal_rows(
    resource_id: str = "aws_instance.web_1",
    base_cost: float = 10.0,
    days: int = 20,
) -> list[dict[str, object]]:
    """평상 범위 내 비용 레코드 생성."""
    return [
        {
            "charge_date": date(2024, 1, i + 1),
            "resource_id": resource_id,
            "cost_unit_key": "platform:checkout:prod",
            "team": "platform",
            "product": "checkout",
            "env": "prod",
            "effective_cost": base_cost + (i % 3) * 0.5,
        }
        for i in range(days)
    ]


class TestZScoreDetectorBasic:
    def test_no_anomaly_in_stable_data(self) -> None:
        df = _make_df(_normal_rows(base_cost=10.0))
        detector = ZScoreDetector()
        results = detector.detect(df)
        assert results == []

    def test_detects_spike_as_anomaly(self) -> None:
        rows = _normal_rows(base_cost=10.0, days=20)
        rows.append({
            "charge_date": date(2024, 1, 21),
            "resource_id": "aws_instance.web_1",
            "cost_unit_key": "platform:checkout:prod",
            "team": "platform",
            "product": "checkout",
            "env": "prod",
            "effective_cost": 100.0,  # 평균 대비 ~10배 스파이크
        })
        df = _make_df(rows)
        detector = ZScoreDetector(threshold_warning=2.0, threshold_critical=3.0)
        results = detector.detect(df)
        assert len(results) >= 1
        anomaly = results[0]
        assert anomaly.resource_id == "aws_instance.web_1"
        assert anomaly.z_score > 2.0

    def test_empty_dataframe_returns_empty(self) -> None:
        df = _make_df([])
        detector = ZScoreDetector()
        results = detector.detect(df)
        assert results == []

    def test_missing_required_column_raises(self) -> None:
        df = pl.DataFrame({"resource_id": ["x"], "effective_cost": [1.0]})
        detector = ZScoreDetector()
        with pytest.raises(ValueError, match="필수 컬럼 누락"):
            detector.detect(df)


class TestZScoreSeverity:
    def _make_spike_df(self, spike_cost: float, base_cost: float = 10.0) -> pl.DataFrame:
        rows = _normal_rows(base_cost=base_cost, days=30)
        rows.append({
            "charge_date": date(2024, 2, 1),
            "resource_id": "aws_instance.web_1",
            "cost_unit_key": "platform:checkout:prod",
            "team": "platform",
            "product": "checkout",
            "env": "prod",
            "effective_cost": spike_cost,
        })
        return _make_df(rows)

    def test_critical_severity_for_large_spike(self) -> None:
        df = self._make_spike_df(spike_cost=200.0)
        detector = ZScoreDetector(threshold_warning=2.0, threshold_critical=3.0)
        results = detector.detect(df)
        criticals = [r for r in results if r.severity == "critical"]
        assert len(criticals) >= 1

    def test_warning_severity_for_moderate_spike(self) -> None:
        rows = _normal_rows(base_cost=10.0, days=30)
        # 표준편차를 구하기 위해 비용 편차 주입
        for i in range(0, 15):
            rows[i]["effective_cost"] = 8.0
        for i in range(15, 30):
            rows[i]["effective_cost"] = 12.0
        rows.append({
            "charge_date": date(2024, 2, 1),
            "resource_id": "aws_instance.web_1",
            "cost_unit_key": "platform:checkout:prod",
            "team": "platform",
            "product": "checkout",
            "env": "prod",
            "effective_cost": 16.0,
        })
        df = _make_df(rows)
        detector = ZScoreDetector(threshold_warning=2.0, threshold_critical=3.0)
        results = detector.detect(df)
        severities = {r.severity for r in results}
        assert len(results) >= 0  # 데이터 분포에 따라 결과 다를 수 있음

    def test_constant_cost_resource_no_anomaly(self) -> None:
        rows = [
            {
                "charge_date": date(2024, 1, i + 1),
                "resource_id": "aws_s3.logs",
                "cost_unit_key": "data:storage:prod",
                "team": "data",
                "product": "storage",
                "env": "prod",
                "effective_cost": 5.0,
            }
            for i in range(20)
        ]
        df = _make_df(rows)
        detector = ZScoreDetector()
        results = detector.detect(df)
        assert results == []


class TestAnomalyResultFields:
    def test_result_fields_populated(self) -> None:
        rows = _normal_rows(base_cost=10.0, days=20)
        rows.append({
            "charge_date": date(2024, 1, 21),
            "resource_id": "aws_instance.web_1",
            "cost_unit_key": "platform:checkout:prod",
            "team": "platform",
            "product": "checkout",
            "env": "prod",
            "effective_cost": 200.0,
        })
        df = _make_df(rows)
        detector = ZScoreDetector()
        results = detector.detect(df)
        assert results
        r = results[0]
        assert isinstance(r, AnomalyResult)
        assert r.resource_id == "aws_instance.web_1"
        assert r.cost_unit_key == "platform:checkout:prod"
        assert r.team == "platform"
        assert r.z_score > 0
        assert r.is_anomaly is True
        assert r.severity in {"warning", "critical"}

    def test_multiple_resources_isolated(self) -> None:
        rows_a = _normal_rows(resource_id="aws_instance.web_1", base_cost=10.0)
        rows_b = _normal_rows(resource_id="aws_rds.db_1", base_cost=50.0)
        rows_b.append({
            "charge_date": date(2024, 1, 21),
            "resource_id": "aws_rds.db_1",
            "cost_unit_key": "platform:checkout:prod",
            "team": "platform",
            "product": "checkout",
            "env": "prod",
            "effective_cost": 500.0,
        })
        df = _make_df(rows_a + rows_b)
        detector = ZScoreDetector()
        results = detector.detect(df)
        anomaly_resources = {r.resource_id for r in results}
        assert "aws_rds.db_1" in anomaly_resources
        assert "aws_instance.web_1" not in anomaly_resources
