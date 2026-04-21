"""MovingAverageDetector — 롤링 이동평균 기반 이상치 탐지."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import polars as pl

from ..core.anomaly_detector import AnomalyResult

_DETECTOR_NAME = "moving_average"


class MovingAverageDetector:
    """롤링 이동평균 + 표준편차로 이상치를 탐지한다.

    window_days 내 이동평균/표준편차를 계산하여 현재 비용이
    mean ± multiplier_warning*std 범위를 벗어나면 이상치로 판단한다.
    """

    name: str = _DETECTOR_NAME

    def __init__(
        self,
        window_days: int = 7,
        multiplier_warning: float = 2.0,
        multiplier_critical: float = 3.0,
        min_window: int = 3,
    ) -> None:
        self.window_days = window_days
        self.multiplier_warning = multiplier_warning
        self.multiplier_critical = multiplier_critical
        self.min_window = min_window

    def detect(self, df: pl.DataFrame) -> list[AnomalyResult]:
        """resource_id + cost_unit_key 그룹별 롤링 이상치 탐지.

        Args:
            df: charge_date, resource_id, cost_unit_key, team, product, env,
                effective_cost 컬럼을 포함하는 DataFrame.

        Returns:
            warning/critical 이상치만 포함하는 AnomalyResult 리스트.
        """
        if df.is_empty():
            return []

        group_keys = ["resource_id", "cost_unit_key", "team", "product", "env"]
        results: list[AnomalyResult] = []

        for group_vals, group_df in df.group_by(group_keys, maintain_order=True):
            if len(group_df) < self.min_window:
                continue

            sorted_df = group_df.sort("charge_date")
            costs = sorted_df["effective_cost"].to_list()
            dates = sorted_df["charge_date"].to_list()

            resource_id: str
            cost_unit_key: str
            team: str
            product: str
            env: str
            resource_id, cost_unit_key, team, product, env = (
                str(group_vals[i]) for i in range(5)
            )

            for i, (cur_date, cur_cost) in enumerate(zip(dates, costs)):
                window_start = max(0, i - self.window_days + 1)
                window = costs[window_start:i]
                if len(window) < self.min_window:
                    continue

                mean_cost = sum(window) / len(window)
                variance = sum((x - mean_cost) ** 2 for x in window) / len(window)
                std_cost = variance ** 0.5

                if std_cost == 0.0:
                    # 윈도우 내 비용이 모두 동일 — 현재값과 다르면 무한 편차
                    if cur_cost == mean_cost:
                        continue
                    z = self.multiplier_critical * 2  # 임계값보다 큰 고정값
                else:
                    z = (cur_cost - mean_cost) / std_cost

                if abs(z) >= self.multiplier_critical:
                    severity = "critical"
                elif abs(z) >= self.multiplier_warning:
                    severity = "warning"
                else:
                    continue

                results.append(
                    AnomalyResult(
                        resource_id=resource_id,
                        cost_unit_key=cost_unit_key,
                        team=team,
                        product=product,
                        env=env,
                        charge_date=cur_date if isinstance(cur_date, date) else date.fromisoformat(str(cur_date)),
                        effective_cost=Decimal(str(cur_cost)),
                        mean_cost=Decimal(str(mean_cost)),
                        std_cost=Decimal(str(std_cost)),
                        z_score=float(z),
                        is_anomaly=True,
                        severity=severity,
                        detector_name=_DETECTOR_NAME,
                    )
                )

        return results
