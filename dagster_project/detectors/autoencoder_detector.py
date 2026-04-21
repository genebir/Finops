"""AutoencoderDetector — MLP Autoencoder 재구성 오차 기반 이상치 탐지."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import polars as pl

from ..core.anomaly_detector import AnomalyResult

logger = logging.getLogger(__name__)

_DETECTOR_NAME = "autoencoder"
_MIN_SAMPLES = 14
_WINDOW_SIZE = 7


class AutoencoderDetector:
    """MLP Autoencoder의 재구성 오차(reconstruction error)로 이상치를 탐지한다.

    resource_id + cost_unit_key 그룹별로 슬라이딩 윈도우 특징을 추출하고,
    scikit-learn MLPRegressor로 autoencoder를 학습한 뒤
    재구성 오차가 threshold × std(재구성 오차)를 초과하면 이상치로 판단한다.
    """

    name: str = _DETECTOR_NAME

    def __init__(
        self,
        window_size: int = _WINDOW_SIZE,
        threshold_warning: float = 2.0,
        threshold_critical: float = 3.0,
        min_samples: int = _MIN_SAMPLES,
        hidden_layer_sizes: tuple[int, ...] = (32, 16, 32),
        max_iter: int = 200,
        random_state: int = 42,
    ) -> None:
        self.window_size = window_size
        self.threshold_warning = threshold_warning
        self.threshold_critical = threshold_critical
        self.min_samples = min_samples
        self.hidden_layer_sizes = hidden_layer_sizes
        self.max_iter = max_iter
        self.random_state = random_state

    def detect(self, df: pl.DataFrame) -> list[AnomalyResult]:
        """resource_id + cost_unit_key 그룹별 Autoencoder 재구성 오차 기반 이상치 탐지.

        Args:
            df: charge_date, resource_id, cost_unit_key, team, product, env,
                effective_cost 컬럼을 포함하는 DataFrame.

        Returns:
            warning/critical 이상치만 포함하는 AnomalyResult 리스트.
        """
        try:
            from sklearn.neural_network import MLPRegressor
            from sklearn.preprocessing import MinMaxScaler
        except ImportError:
            logger.warning("scikit-learn 미설치 — AutoencoderDetector 건너뜀")
            return []

        if df.is_empty():
            return []

        group_keys = ["resource_id", "cost_unit_key", "team", "product", "env"]
        results: list[AnomalyResult] = []

        for group_vals, group_df in df.group_by(group_keys, maintain_order=True):
            if len(group_df) < self.min_samples + self.window_size:
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
                # 슬라이딩 윈도우 특징 행렬 생성
                scaler = MinMaxScaler()
                costs_arr = [[c] for c in costs]
                scaled = scaler.fit_transform(costs_arr)
                flat = [float(x[0]) for x in scaled]

                X = []
                for i in range(len(flat) - self.window_size):
                    X.append(flat[i: i + self.window_size])

                if len(X) < self.min_samples:
                    continue

                model = MLPRegressor(
                    hidden_layer_sizes=self.hidden_layer_sizes,
                    max_iter=self.max_iter,
                    random_state=self.random_state,
                )
                model.fit(X, X)  # autoencoder: input == target

                reconstructed = model.predict(X)
                errors = [
                    sum((a - b) ** 2 for a, b in zip(orig, rec)) / self.window_size
                    for orig, rec in zip(X, reconstructed)
                ]
            except Exception as exc:
                logger.warning(f"Autoencoder fit failed for {resource_id}: {exc}")
                continue

            if len(errors) < 2:
                continue

            mean_err = sum(errors) / len(errors)
            var_err = sum((e - mean_err) ** 2 for e in errors) / len(errors)
            std_err = var_err ** 0.5

            if std_err == 0.0:
                continue

            offset = self.window_size
            for i, (error, cur_date) in enumerate(
                zip(errors, dates[offset:])
            ):
                z = (error - mean_err) / std_err
                if z >= self.threshold_critical:
                    severity = "critical"
                elif z >= self.threshold_warning:
                    severity = "warning"
                else:
                    continue

                cur_cost = costs[i + offset]
                mean_cost = float(sum(costs[max(0, i): i + offset]) / min(self.window_size, i + offset))
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
                        mean_cost=Decimal(str(round(mean_cost, 6))),
                        std_cost=Decimal(str(round(std_err, 6))),
                        z_score=round(z, 6),
                        is_anomaly=True,
                        severity=severity,
                        detector_name=_DETECTOR_NAME,
                    )
                )

        return results
