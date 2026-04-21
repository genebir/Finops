"""ArimaDetector — ARIMA 시계열 모델 기반 이상치 탐지."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import polars as pl

from ..core.anomaly_detector import AnomalyResult

logger = logging.getLogger(__name__)

_DETECTOR_NAME = "arima"
_MIN_SAMPLES = 10


class ArimaDetector:
    """ARIMA 모델 잔차(residual) 기반 이상치 탐지기.

    resource_id + cost_unit_key 그룹별로 ARIMA(p,d,q) 모델을 피팅하고,
    실제값과 예측값의 차이(잔차)가 임계값 × 잔차표준편차를 초과하면 이상치로 판단한다.
    """

    name: str = _DETECTOR_NAME

    def __init__(
        self,
        order: tuple[int, int, int] = (1, 1, 1),
        threshold_warning: float = 2.0,
        threshold_critical: float = 3.0,
        min_samples: int = _MIN_SAMPLES,
    ) -> None:
        self.order = order
        self.threshold_warning = threshold_warning
        self.threshold_critical = threshold_critical
        self.min_samples = min_samples

    def detect(self, df: pl.DataFrame) -> list[AnomalyResult]:
        """resource_id + cost_unit_key 그룹별 ARIMA 잔차 기반 이상치 탐지.

        Args:
            df: charge_date, resource_id, cost_unit_key, team, product, env,
                effective_cost 컬럼을 포함하는 DataFrame.

        Returns:
            warning/critical 이상치만 포함하는 AnomalyResult 리스트.
        """
        try:
            from statsmodels.tsa.arima.model import ARIMA
        except ImportError:
            logger.warning("statsmodels 미설치 — ArimaDetector 건너뜀")
            return []

        if df.is_empty():
            return []

        group_keys = ["resource_id", "cost_unit_key", "team", "product", "env"]
        results: list[AnomalyResult] = []

        for group_vals, group_df in df.group_by(group_keys, maintain_order=True):
            if len(group_df) < self.min_samples:
                continue

            sorted_df = group_df.sort("charge_date")
            costs = sorted_df["effective_cost"].to_list()
            dates = sorted_df["charge_date"].to_list()

            resource_id = str(group_vals[0])
            cost_unit_key = str(group_vals[1])
            team = str(group_vals[2])
            product = str(group_vals[3])
            env = str(group_vals[4])

            try:
                model = ARIMA(costs, order=self.order)
                fit = model.fit()
                residuals = [
                    float(a) - float(p)
                    for a, p in zip(costs, fit.fittedvalues)
                ]
            except Exception as exc:
                logger.warning(f"ARIMA fit failed for {resource_id}: {exc}")
                continue

            if len(residuals) < 2:
                continue

            mean_res = sum(residuals) / len(residuals)
            var_res = sum((r - mean_res) ** 2 for r in residuals) / len(residuals)
            std_res = var_res ** 0.5

            if std_res == 0.0:
                continue

            for i, (cur_date, cur_cost, residual) in enumerate(
                zip(dates, costs, residuals)
            ):
                z = abs(residual) / std_res
                if z >= self.threshold_critical:
                    severity = "critical"
                elif z >= self.threshold_warning:
                    severity = "warning"
                else:
                    continue

                mean_cost = float(fit.fittedvalues[i])
                results.append(
                    AnomalyResult(
                        resource_id=resource_id,
                        cost_unit_key=cost_unit_key,
                        team=team,
                        product=product,
                        env=env,
                        charge_date=(
                            cur_date
                            if isinstance(cur_date, date)
                            else date.fromisoformat(str(cur_date))
                        ),
                        effective_cost=Decimal(str(cur_cost)),
                        mean_cost=Decimal(str(mean_cost)),
                        std_cost=Decimal(str(std_res)),
                        z_score=float(residual) / std_res,
                        is_anomaly=True,
                        severity=severity,
                        detector_name=_DETECTOR_NAME,
                    )
                )

        return results
