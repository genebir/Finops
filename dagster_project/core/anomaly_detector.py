"""AnomalyDetector Protocol — 이상치 탐지 추상 인터페이스."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

import polars as pl


@dataclass
class AnomalyResult:
    """단일 레코드에 대한 이상치 탐지 결과."""

    resource_id: str
    cost_unit_key: str
    team: str
    product: str
    env: str
    charge_date: date
    effective_cost: Decimal
    mean_cost: Decimal
    std_cost: Decimal
    z_score: float
    is_anomaly: bool
    severity: str        # "critical" | "warning" | "ok"
    detector_name: str = "zscore"  # "zscore" | "isolation_forest"


class AnomalyDetector(Protocol):
    """비용 데이터에서 이상치를 탐지하는 인터페이스.

    Phase 2 구현체: ZScoreDetector
    Phase 3 예정: IsolationForestDetector
    """

    name: str
    threshold_warning: float   # Z-score 경고 임계값 (기본 2.0)
    threshold_critical: float  # Z-score 위험 임계값 (기본 3.0)

    def detect(self, df: pl.DataFrame) -> list[AnomalyResult]:
        """fact_daily_cost 형태의 DataFrame에서 이상치를 탐지한다.

        Args:
            df: charge_date, resource_id, cost_unit_key, team, product, env,
                effective_cost 컬럼을 포함하는 DataFrame.

        Returns:
            is_anomaly=True인 레코드만 포함한 AnomalyResult 리스트.
        """
        ...
