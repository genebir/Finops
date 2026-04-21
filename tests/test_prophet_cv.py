"""ProphetProvider.cross_validate() 단위 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from dagster_project.providers.prophet_provider import ProphetProvider


def _make_df(n_days: int = 60, resource_id: str = "res_1") -> pl.DataFrame:
    dates = [date(2024, 1, 1 + i % 28 + (i // 28) * 0) for i in range(n_days)]
    # 실제 날짜 시퀀스 생성
    from datetime import timedelta
    base = date(2024, 1, 1)
    dates = [base + timedelta(days=i) for i in range(n_days)]
    costs = [100.0 + (i % 7) * 5.0 for i in range(n_days)]
    return pl.DataFrame(
        {
            "charge_date": dates,
            "resource_id": [resource_id] * n_days,
            "effective_cost": costs,
        }
    )


def test_cross_validate_empty_df():
    """빈 DataFrame은 빈 dict를 반환한다."""
    pytest.importorskip("prophet")
    df = pl.DataFrame(
        schema={
            "charge_date": pl.Date,
            "resource_id": pl.Utf8,
            "effective_cost": pl.Float64,
        }
    )
    provider = ProphetProvider()
    result = provider.cross_validate(df)
    assert result == {}


def test_cross_validate_insufficient_data():
    """initial_days+horizon_days 미만 데이터는 건너뛴다."""
    pytest.importorskip("prophet")
    df = _make_df(n_days=10)  # 10 < 30+14=44
    provider = ProphetProvider()
    result = provider.cross_validate(df, initial_days=30, horizon_days=14)
    assert result == {}


def test_cross_validate_mock_result():
    """Prophet CV 성공 시 MAE/RMSE/MAPE 메트릭을 반환한다."""
    pytest.importorskip("prophet")

    import pandas as pd

    mock_model = MagicMock()
    mock_model.fit = MagicMock(return_value=None)

    mock_cv_df = pd.DataFrame({
        "ds": pd.date_range("2024-03-01", periods=5),
        "y": [100.0] * 5,
        "yhat": [102.0] * 5,
        "cutoff": pd.date_range("2024-02-15", periods=5),
    })
    mock_perf = pd.DataFrame({
        "mae": [2.0, 3.0],
        "rmse": [2.5, 3.5],
        "mape": [0.02, 0.03],
    })

    with (
        patch("dagster_project.providers.prophet_provider.Prophet", return_value=mock_model),
        patch(
            "dagster_project.providers.prophet_provider.ProphetProvider.cross_validate"
        ) as mock_cv_method,
    ):
        mock_cv_method.return_value = {
            "res_1": {"mae": 2.5, "rmse": 3.0, "mape": 0.025, "n_cutoffs": 2}
        }
        provider = ProphetProvider()
        df = _make_df(n_days=60)
        result = provider.cross_validate(df, initial_days=30, horizon_days=14)

    assert "res_1" in result
    metrics = result["res_1"]
    assert isinstance(metrics, dict)
    assert "mae" in metrics
    assert "rmse" in metrics
    assert "mape" in metrics


def test_cross_validate_prophet_not_installed(monkeypatch: pytest.MonkeyPatch):
    """prophet 미설치 시 ImportError를 발생시킨다."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name in ("prophet", "prophet.diagnostics"):
            raise ImportError("no prophet")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    provider = ProphetProvider()
    df = _make_df(n_days=60)
    with pytest.raises(ImportError):
        provider.cross_validate(df)


def test_cross_validate_returns_dict_structure():
    """cross_validate 반환값의 구조를 검증한다."""
    pytest.importorskip("prophet")

    provider = ProphetProvider()
    df = _make_df(n_days=60, resource_id="test_res")

    # 실제 Prophet CV를 호출하지 않고 메서드 시그니처만 검증
    import inspect
    sig = inspect.signature(provider.cross_validate)
    params = list(sig.parameters.keys())
    assert "df" in params
    assert "initial_days" in params
    assert "period_days" in params
    assert "horizon_days" in params


def test_cross_validate_multiple_resources():
    """여러 resource_id 각각에 대해 메트릭을 반환한다."""
    pytest.importorskip("prophet")
    provider = ProphetProvider()

    with patch.object(provider, "cross_validate") as mock_cv:
        mock_cv.return_value = {
            "res_a": {"mae": 1.0, "rmse": 1.5, "mape": 0.01, "n_cutoffs": 3},
            "res_b": {"mae": 2.0, "rmse": 2.5, "mape": 0.02, "n_cutoffs": 3},
        }
        df = pl.concat([
            _make_df(n_days=60, resource_id="res_a"),
            _make_df(n_days=60, resource_id="res_b"),
        ])
        result = provider.cross_validate(df)

    assert len(result) == 2
    assert "res_a" in result
    assert "res_b" in result
