"""ZScoreDetector — Z-score 기반 이상치 탐지 구현체."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import polars as pl

from ..core.anomaly_detector import AnomalyResult


class ZScoreDetector:
    """resource_id + cost_unit_key 그룹별 Z-score로 이상치를 탐지한다.

    각 리소스의 전체 기간 평균/표준편차를 기준으로 Z-score를 계산한다.
    표준편차가 0인 경우(비용이 일정한 리소스)는 이상치에서 제외된다.
    """

    name: str = "zscore"

    def __init__(
        self,
        threshold_warning: float = 2.0,
        threshold_critical: float = 3.0,
    ) -> None:
        self.threshold_warning = threshold_warning
        self.threshold_critical = threshold_critical

    def detect(self, df: pl.DataFrame) -> list[AnomalyResult]:
        """fact_daily_cost DataFrame에서 Z-score 기반 이상치를 탐지한다.

        Args:
            df: charge_date, resource_id, cost_unit_key, team, product, env,
                effective_cost 컬럼을 포함하는 DataFrame.

        Returns:
            severity가 "warning" 또는 "critical"인 AnomalyResult 리스트.
        """
        required_cols = {
            "charge_date", "resource_id", "cost_unit_key",
            "team", "product", "env", "effective_cost",
        }
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame에 필수 컬럼 누락: {missing}")

        if df.is_empty():
            return []

        group_stats = (
            df.group_by(["resource_id", "cost_unit_key", "team", "product", "env"])
            .agg([
                pl.col("effective_cost").mean().alias("mean_cost"),
                pl.col("effective_cost").std(ddof=1).alias("std_cost"),
            ])
        )

        enriched = df.join(
            group_stats,
            on=["resource_id", "cost_unit_key", "team", "product", "env"],
            how="left",
        )

        enriched = enriched.with_columns([
            pl.when(
                pl.col("std_cost").is_null() | (pl.col("std_cost") == 0.0)
            )
            .then(pl.lit(0.0))
            .otherwise(
                (pl.col("effective_cost") - pl.col("mean_cost")) / pl.col("std_cost")
            )
            .alias("z_score"),
        ])

        threshold_warning = self.threshold_warning
        threshold_critical = self.threshold_critical

        enriched = enriched.with_columns([
            (pl.col("z_score").abs() > threshold_warning).alias("is_anomaly"),
            pl.when(pl.col("z_score").abs() > threshold_critical)
            .then(pl.lit("critical"))
            .when(pl.col("z_score").abs() > threshold_warning)
            .then(pl.lit("warning"))
            .otherwise(pl.lit("ok"))
            .alias("severity"),
        ])

        anomalies = enriched.filter(pl.col("is_anomaly"))

        results: list[AnomalyResult] = []
        for row in anomalies.iter_rows(named=True):
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
                    resource_id=str(row["resource_id"]),
                    cost_unit_key=str(row["cost_unit_key"]),
                    team=str(row["team"]),
                    product=str(row["product"]),
                    env=str(row["env"]),
                    charge_date=charge_date,
                    effective_cost=Decimal(str(row["effective_cost"])),
                    mean_cost=Decimal(str(row["mean_cost"])),
                    std_cost=Decimal(str(row["std_cost"] or 0)),
                    z_score=float(row["z_score"]),
                    is_anomaly=bool(row["is_anomaly"]),
                    severity=str(row["severity"]),
                    detector_name="zscore",
                )
            )

        return results
