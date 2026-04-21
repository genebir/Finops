"""Prophet 예측 Provider 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from dagster_project.providers.prophet_provider import ProphetProvider, _MIN_TRAINING_DAYS


def _make_df(
    resource_id: str = "aws_instance.web_1",
    base_cost: float = 10.0,
    days: int = 30,
    start_date: date = date(2024, 1, 1),
) -> pl.DataFrame:
    from datetime import timedelta

    rows = [
        {
            "charge_date": (start_date + timedelta(days=i)).isoformat(),
            "resource_id": resource_id,
            "effective_cost": base_cost + (i % 5) * 0.2,
        }
        for i in range(days)
    ]
    return pl.DataFrame(rows).with_columns(
        pl.col("charge_date").str.to_date()
    )


class TestProphetProviderInit:
    def test_default_params(self) -> None:
        p = ProphetProvider()
        assert p.name == "prophet"
        assert p.forecast_horizon_days == 30
        assert p.seasonality_mode == "multiplicative"

    def test_custom_params(self) -> None:
        p = ProphetProvider(forecast_horizon_days=14, seasonality_mode="additive")
        assert p.forecast_horizon_days == 14
        assert p.seasonality_mode == "additive"


class TestProphetProviderMissingColumns:
    def test_missing_columns_raises(self) -> None:
        df = pl.DataFrame({"resource_id": ["x"], "effective_cost": [1.0]})
        provider = ProphetProvider()
        with pytest.raises(ValueError, match="필수 컬럼 누락"):
            provider.forecast_from_df(df)

    def test_empty_df_returns_empty(self) -> None:
        df = pl.DataFrame(
            schema={"charge_date": pl.Date, "resource_id": pl.Utf8, "effective_cost": pl.Float64}
        )
        provider = ProphetProvider()
        with patch("dagster_project.providers.prophet_provider.Prophet"):
            results = provider.forecast_from_df(df)
        assert results == []


class TestProphetProviderInsufficientData:
    def test_skips_resource_with_few_days(self) -> None:
        df = _make_df(days=_MIN_TRAINING_DAYS - 1)
        provider = ProphetProvider()
        with patch("dagster_project.providers.prophet_provider.Prophet") as mock_prophet:
            results = provider.forecast_from_df(df)
        mock_prophet.assert_not_called()
        assert results == []

    def test_includes_resource_with_sufficient_days(self) -> None:
        df = _make_df(days=_MIN_TRAINING_DAYS)
        provider = ProphetProvider()

        mock_model = MagicMock()
        mock_future = MagicMock()
        import pandas as pd

        mock_forecast = pd.DataFrame({"yhat": [10.0] * 30})
        mock_model.make_future_dataframe.return_value = mock_future
        mock_model.predict.return_value = mock_forecast

        with patch(
            "dagster_project.providers.prophet_provider.Prophet",
            return_value=mock_model,
        ):
            results = provider.forecast_from_df(df)

        assert len(results) == 1
        assert results[0].resource_address == "aws_instance.web_1"
        assert results[0].currency == "USD"


class TestProphetForecastRecord:
    def test_monthly_cost_is_sum_of_horizon(self) -> None:
        df = _make_df(days=30)
        provider = ProphetProvider(forecast_horizon_days=10)

        mock_model = MagicMock()
        mock_future = MagicMock()
        import pandas as pd

        yhat_values = [5.0] * 10
        mock_forecast = pd.DataFrame({"yhat": yhat_values})
        mock_model.make_future_dataframe.return_value = mock_future
        mock_model.predict.return_value = mock_forecast

        with patch(
            "dagster_project.providers.prophet_provider.Prophet",
            return_value=mock_model,
        ):
            results = provider.forecast_from_df(df)

        assert len(results) == 1
        assert float(results[0].monthly_cost) == pytest.approx(50.0, abs=0.01)

    def test_negative_yhat_clipped_to_zero(self) -> None:
        df = _make_df(days=20)
        provider = ProphetProvider(forecast_horizon_days=5)

        mock_model = MagicMock()
        mock_future = MagicMock()
        import pandas as pd

        mock_forecast = pd.DataFrame({"yhat": [-10.0] * 5})
        mock_model.make_future_dataframe.return_value = mock_future
        mock_model.predict.return_value = mock_forecast

        with patch(
            "dagster_project.providers.prophet_provider.Prophet",
            return_value=mock_model,
        ):
            results = provider.forecast_from_df(df)

        assert len(results) == 1
        assert float(results[0].monthly_cost) == 0.0

    def test_multiple_resources(self) -> None:
        df_a = _make_df(resource_id="aws_instance.web_1", days=20)
        df_b = _make_df(resource_id="aws_rds.db_1", days=20, base_cost=50.0)
        df = pl.concat([df_a, df_b])
        provider = ProphetProvider()

        mock_model = MagicMock()
        mock_future = MagicMock()
        import pandas as pd

        mock_forecast = pd.DataFrame({"yhat": [10.0] * 30})
        mock_model.make_future_dataframe.return_value = mock_future
        mock_model.predict.return_value = mock_forecast

        with patch(
            "dagster_project.providers.prophet_provider.Prophet",
            return_value=mock_model,
        ):
            results = provider.forecast_from_df(df)

        assert len(results) == 2
        addresses = {r.resource_address for r in results}
        assert "aws_instance.web_1" in addresses
        assert "aws_rds.db_1" in addresses


class TestProphetForecastProtocol:
    def test_forecast_scope_returns_empty_list(self) -> None:
        from dagster_project.core.forecast_provider import ForecastScope

        provider = ProphetProvider()
        result = provider.forecast(ForecastScope(terraform_path="terraform/sample"))
        assert result == []

    def test_forecast_from_df_raises_when_prophet_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import dagster_project.providers.prophet_provider as mod

        monkeypatch.setattr(mod, "Prophet", None)
        provider = ProphetProvider()
        df = _make_df(days=20)
        with pytest.raises(ImportError, match="prophet"):
            provider.forecast_from_df(df)
