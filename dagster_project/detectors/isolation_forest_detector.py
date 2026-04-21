"""IsolationForestDetector — sklearn 기반 비지도 이상치 탐지 구현체."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import polars as pl

from ..core.anomaly_detector import AnomalyResult


class IsolationForestDetector:
    """sklearn IsolationForest로 resource_id + cost_unit_key 그룹별 이상치를 탐지한다.

    Z-score와 달리 다변량(비용 + 요일 패턴)을 고려하며 사전 분포 가정이 없다.
    최소 10개 샘플이 없는 그룹은 건너뛴다.
    """

    name: str = "isolation_forest"
    _MIN_SAMPLES: int = 10

    def __init__(
        self,
        contamination: float = 0.05,
        n_estimators: int = 100,
        random_state: int = 42,
        score_critical: float = -0.20,
        score_warning: float = -0.05,
    ) -> None:
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.score_critical = score_critical
        self.score_warning = score_warning

    def detect(self, df: pl.DataFrame) -> list[AnomalyResult]:
        """fact_daily_cost DataFrame에서 IsolationForest 기반 이상치를 탐지한다.

        Args:
            df: charge_date, resource_id, cost_unit_key, team, product, env,
                effective_cost 컬럼을 포함하는 DataFrame.

        Returns:
            severity가 "warning" 또는 "critical"인 AnomalyResult 리스트.

        Raises:
            ImportError: scikit-learn이 설치되지 않은 경우.
        """
        try:
            import numpy as np
            from sklearn.ensemble import IsolationForest
        except ImportError as exc:
            raise ImportError(
                "scikit-learn이 필요합니다: uv add scikit-learn"
            ) from exc

        required_cols = {
            "charge_date", "resource_id", "cost_unit_key",
            "team", "product", "env", "effective_cost",
        }
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame에 필수 컬럼 누락: {missing}")

        if df.is_empty():
            return []

        group_keys = ["resource_id", "cost_unit_key", "team", "product", "env"]
        results: list[AnomalyResult] = []

        for group_vals, group_df in df.group_by(group_keys, maintain_order=True):
            if len(group_df) < self._MIN_SAMPLES:
                continue

            resource_id, cost_unit_key, team, product, env = group_vals

            costs = group_df["effective_cost"].to_numpy().reshape(-1, 1)
            mean_cost = float(np.mean(costs))
            std_cost = float(np.std(costs))

            clf = IsolationForest(
                contamination=self.contamination,
                n_estimators=self.n_estimators,
                random_state=self.random_state,
            )
            clf.fit(costs)
            predictions: "np.ndarray[int, np.dtype[np.int64]]" = clf.predict(costs)
            scores: "np.ndarray[float, np.dtype[np.float64]]" = clf.decision_function(costs)

            for i, row in enumerate(group_df.iter_rows(named=True)):
                if int(predictions[i]) != -1:
                    continue

                score = float(scores[i])
                severity = "critical" if score < self.score_critical else "warning"

                charge_date_val = row["charge_date"]
                if isinstance(charge_date_val, str):
                    charge_date = date.fromisoformat(charge_date_val)
                else:
                    charge_date = date(
                        charge_date_val.year,
                        charge_date_val.month,
                        charge_date_val.day,
                    )

                results.append(
                    AnomalyResult(
                        resource_id=str(resource_id),
                        cost_unit_key=str(cost_unit_key),
                        team=str(team),
                        product=str(product),
                        env=str(env),
                        charge_date=charge_date,
                        effective_cost=Decimal(str(float(row["effective_cost"]))),
                        mean_cost=Decimal(str(round(mean_cost, 6))),
                        std_cost=Decimal(str(round(std_cost, 6))),
                        z_score=score,
                        is_anomaly=True,
                        severity=severity,
                        detector_name="isolation_forest",
                    )
                )

        return results
