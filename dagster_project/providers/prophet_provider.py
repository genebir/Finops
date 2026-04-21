"""ProphetProvider — Facebook Prophet 기반 시계열 비용 예측 구현체."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

import polars as pl

from ..config import load_config
from ..core.forecast_provider import ForecastRecord, ForecastScope

logger = logging.getLogger(__name__)

_cfg = load_config()
_MIN_TRAINING_DAYS: int = _cfg.prophet.min_training_days

try:
    from prophet import Prophet
except ImportError:
    Prophet = None


class ProphetProvider:
    """Facebook Prophet으로 resource_id별 일별 비용 시계열을 학습하고 다음 달을 예측한다.

    Phase 2 구현체. ForecastProvider Protocol을 준수한다.
    데이터가 MIN_TRAINING_DAYS(14일) 미만인 리소스는 예측에서 제외된다.
    """

    name: str = "prophet"

    def __init__(
        self,
        forecast_horizon_days: int = 30,
        seasonality_mode: str = "multiplicative",
    ) -> None:
        self.forecast_horizon_days = forecast_horizon_days
        self.seasonality_mode = seasonality_mode

    def forecast_from_df(self, df: pl.DataFrame) -> list[ForecastRecord]:
        """fact_daily_cost 형태의 DataFrame으로부터 Prophet 예측을 수행한다.

        Args:
            df: charge_date, resource_id, effective_cost 컬럼을 포함하는 DataFrame.

        Returns:
            리소스별 예측 월비용 ForecastRecord 리스트.
        """
        if Prophet is None:
            raise ImportError("prophet 패키지가 필요합니다: uv add prophet")

        required = {"charge_date", "resource_id", "effective_cost"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame에 필수 컬럼 누락: {missing}")

        records: list[ForecastRecord] = []
        now = datetime.now(tz=UTC)

        resource_ids = df["resource_id"].unique().to_list()
        for resource_id in resource_ids:
            sub = (
                df.filter(pl.col("resource_id") == resource_id)
                .select(["charge_date", "effective_cost"])
                .sort("charge_date")
            )

            if len(sub) < _MIN_TRAINING_DAYS:
                logger.warning(
                    "리소스 %s 학습 데이터 부족 (%d일 < %d일) — 예측 제외",
                    resource_id,
                    len(sub),
                    _MIN_TRAINING_DAYS,
                )
                continue

            prophet_df = sub.rename(
                {"charge_date": "ds", "effective_cost": "y"}
            ).to_pandas()
            prophet_df["ds"] = prophet_df["ds"].astype(str)

            try:
                model = Prophet(
                    seasonality_mode=self.seasonality_mode,
                    daily_seasonality=False,
                    weekly_seasonality=True,
                    yearly_seasonality=False,
                )
                model.fit(prophet_df)

                future = model.make_future_dataframe(
                    periods=self.forecast_horizon_days, freq="D"
                )
                forecast = model.predict(future)

                horizon_rows = forecast.tail(self.forecast_horizon_days)
                monthly_cost = Decimal(
                    str(round(max(float(horizon_rows["yhat"].sum()), 0.0), 6))
                )
                lower_sum = (
                    float(horizon_rows["yhat_lower"].sum())
                    if "yhat_lower" in horizon_rows.columns
                    else 0.0
                )
                upper_sum = (
                    float(horizon_rows["yhat_upper"].sum())
                    if "yhat_upper" in horizon_rows.columns
                    else float(monthly_cost)
                )
                lower_bound = Decimal(str(round(max(lower_sum, 0.0), 6)))
                upper_bound = Decimal(str(round(max(upper_sum, 0.0), 6)))
                hourly_cost = (monthly_cost / Decimal(str(_cfg.prophet.hours_per_month))).quantize(
                    Decimal("0.000001")
                )

                records.append(
                    ForecastRecord(
                        resource_address=str(resource_id),
                        monthly_cost=monthly_cost,
                        hourly_cost=hourly_cost,
                        currency="USD",
                        forecast_generated_at=now,
                        lower_bound_monthly_cost=lower_bound,
                        upper_bound_monthly_cost=upper_bound,
                    )
                )
            except Exception:
                logger.exception("Prophet 예측 실패: %s — 건너뜀", resource_id)
                continue

        logger.info("ProphetProvider: %d/%d 리소스 예측 완료", len(records), len(resource_ids))
        return records

    def forecast(self, scope: ForecastScope) -> list[ForecastRecord]:
        """ForecastProvider Protocol 구현. DuckDB에서 직접 읽지 않으므로 빈 리스트 반환.

        실제 사용은 forecast_from_df()를 통해 prophet_forecast asset에서 호출한다.
        """
        logger.warning(
            "ProphetProvider.forecast()는 ForecastScope를 직접 지원하지 않습니다. "
            "prophet_forecast asset에서 forecast_from_df()를 사용하세요."
        )
        return []

    def cross_validate(
        self,
        df: pl.DataFrame,
        initial_days: int = 30,
        period_days: int = 7,
        horizon_days: int = 14,
    ) -> dict[str, object]:
        """Prophet Cross-Validation으로 예측 모델 정확도를 평가한다.

        Args:
            df: charge_date, resource_id, effective_cost 컬럼을 포함하는 DataFrame.
            initial_days: 초기 학습 기간(일).
            period_days: 교차 검증 슬라이딩 윈도우 간격(일).
            horizon_days: 예측 지평선(일).

        Returns:
            resource_id별 MAE / RMSE / MAPE 메트릭을 담은 dict.
        """
        try:
            from prophet import Prophet
            from prophet.diagnostics import cross_validation, performance_metrics
        except ImportError:
            raise ImportError("prophet 패키지가 필요합니다: uv add prophet")

        if df.is_empty():
            return {}

        metrics: dict[str, object] = {}
        resource_ids = df["resource_id"].unique().to_list()

        for resource_id in resource_ids:
            sub = (
                df.filter(pl.col("resource_id") == resource_id)
                .select(["charge_date", "effective_cost"])
                .sort("charge_date")
            )
            if len(sub) < initial_days + horizon_days:
                logger.warning("CV 건너뜀 (데이터 부족): %s", resource_id)
                continue

            prophet_df = sub.rename(
                {"charge_date": "ds", "effective_cost": "y"}
            ).to_pandas()
            prophet_df["ds"] = prophet_df["ds"].astype(str)

            try:
                model = Prophet(
                    seasonality_mode=self.seasonality_mode,
                    daily_seasonality=False,
                    weekly_seasonality=True,
                    yearly_seasonality=False,
                )
                model.fit(prophet_df)
                df_cv = cross_validation(
                    model,
                    initial=f"{initial_days} days",
                    period=f"{period_days} days",
                    horizon=f"{horizon_days} days",
                    disable_tqdm=True,
                )
                perf = performance_metrics(df_cv)
                metrics[str(resource_id)] = {
                    "mae": float(perf["mae"].mean()),
                    "rmse": float(perf["rmse"].mean()),
                    "mape": float(perf["mape"].mean()),
                    "n_cutoffs": len(perf),
                }
            except Exception as exc:
                logger.warning("Prophet CV 실패: %s — %s", resource_id, exc)

        logger.info("ProphetProvider CV: %d/%d 리소스 평가 완료", len(metrics), len(resource_ids))
        return metrics
