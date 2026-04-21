"""FX Provider 테스트 — StaticFxProvider 동작 검증."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from dagster_project.core.fx_provider import FxRate
from dagster_project.providers.static_fx_provider import StaticFxProvider


class TestStaticFxProvider:
    def test_usd_to_usd_returns_one(self) -> None:
        provider = StaticFxProvider()
        rate = provider.get_rate("USD", "USD")
        assert rate == Decimal("1.0")

    def test_usd_to_eur(self) -> None:
        provider = StaticFxProvider()
        rate = provider.get_rate("USD", "EUR")
        assert rate == Decimal("0.92")

    def test_usd_to_krw(self) -> None:
        provider = StaticFxProvider()
        rate = provider.get_rate("USD", "KRW")
        assert rate == Decimal("1350.0")

    def test_unknown_base_raises(self) -> None:
        provider = StaticFxProvider()
        with pytest.raises(KeyError, match="base currency"):
            provider.get_rate("XYZ", "USD")

    def test_unknown_target_raises(self) -> None:
        provider = StaticFxProvider()
        with pytest.raises(KeyError, match="target currency"):
            provider.get_rate("USD", "XYZ")

    def test_get_all_rates_returns_list(self) -> None:
        provider = StaticFxProvider()
        rates = provider.get_all_rates(base="USD")
        assert len(rates) > 0
        assert all(isinstance(r, FxRate) for r in rates)

    def test_get_all_rates_base_currency(self) -> None:
        provider = StaticFxProvider()
        rates = provider.get_all_rates(base="USD")
        assert all(r.base_currency == "USD" for r in rates)

    def test_get_all_rates_unknown_base_raises(self) -> None:
        provider = StaticFxProvider()
        with pytest.raises(KeyError):
            provider.get_all_rates(base="XYZ")

    def test_get_all_rates_source_is_static(self) -> None:
        provider = StaticFxProvider()
        rates = provider.get_all_rates()
        assert all(r.source == "static" for r in rates)

    def test_convert_usd_to_krw(self) -> None:
        provider = StaticFxProvider()
        result = provider.convert(Decimal("100"), "USD", "KRW")
        assert result == Decimal("135000.0")

    def test_convert_same_currency(self) -> None:
        provider = StaticFxProvider()
        result = provider.convert(Decimal("50.0"), "USD", "USD")
        assert result == Decimal("50.0")

    def test_custom_rates(self) -> None:
        rates = {"USD": Decimal("1.0"), "EUR": Decimal("0.9")}
        provider = StaticFxProvider(rates=rates)
        assert provider.get_rate("USD", "EUR") == Decimal("0.9")

    def test_as_of_param_ignored(self) -> None:
        provider = StaticFxProvider()
        rate = provider.get_rate("USD", "EUR", as_of=date(2020, 1, 1))
        assert rate == Decimal("0.92")

    def test_fx_rate_dataclass_fields(self) -> None:
        provider = StaticFxProvider()
        rates = provider.get_all_rates()
        usd_rate = next(r for r in rates if r.target_currency == "USD")
        assert usd_rate.rate == Decimal("1.0")
        assert isinstance(usd_rate.effective_date, date)

    def test_name_attribute(self) -> None:
        provider = StaticFxProvider()
        assert provider.name == "static"
