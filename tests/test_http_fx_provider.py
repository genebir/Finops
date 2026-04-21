"""HttpFxProvider 단위 테스트."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from dagster_project.providers.http_fx_provider import HttpFxProvider
from dagster_project.providers.static_fx_provider import StaticFxProvider


def _mock_urlopen(response_data: dict[str, object]):
    """urlopen을 mock해서 JSON 응답을 반환하는 컨텍스트 매니저."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_get_rate_success():
    """API 성공 시 환율을 반환한다."""
    data = {"result": "success", "rates": {"KRW": 1350.0, "EUR": 0.92}}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(data)):
        provider = HttpFxProvider(fallback_on_error=False)
        rate = provider.get_rate("USD", "KRW")
    assert rate == Decimal("1350.0")


def test_get_rate_same_currency():
    """동일 통화는 1.0을 반환한다."""
    provider = HttpFxProvider()
    assert provider.get_rate("USD", "USD") == Decimal("1.0")


def test_get_rate_fallback_on_network_error():
    """네트워크 오류 시 StaticFxProvider로 폴백한다."""
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        provider = HttpFxProvider(fallback_on_error=True)
        rate = provider.get_rate("USD", "KRW")
    assert rate > Decimal("0")  # StaticFxProvider 값


def test_get_rate_api_error_fallback():
    """API error-type 응답 시 폴백한다."""
    data = {"result": "error", "error-type": "invalid-key"}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(data)):
        provider = HttpFxProvider(fallback_on_error=True)
        rate = provider.get_rate("USD", "EUR")
    assert rate > Decimal("0")


def test_get_rate_no_fallback_raises():
    """폴백 없이 실패 시 KeyError를 발생시킨다."""
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("fail")):
        provider = HttpFxProvider(fallback_on_error=False)
        with pytest.raises(KeyError):
            provider.get_rate("USD", "EUR")


def test_get_all_rates_success():
    """API 성공 시 FxRate 리스트를 반환한다."""
    data = {"result": "success", "rates": {"KRW": 1350.0, "EUR": 0.92, "JPY": 150.0}}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(data)):
        provider = HttpFxProvider(fallback_on_error=False)
        rates = provider.get_all_rates("USD")
    assert len(rates) == 3
    targets = {r.target_currency for r in rates}
    assert {"KRW", "EUR", "JPY"} == targets
    for r in rates:
        assert r.base_currency == "USD"
        assert r.source == "http"


def test_get_all_rates_fallback():
    """API 실패 시 StaticFxProvider 환율 목록을 반환한다."""
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("fail")):
        provider = HttpFxProvider(fallback_on_error=True)
        rates = provider.get_all_rates("USD")
    assert len(rates) > 0


def test_get_all_rates_no_fallback_empty():
    """폴백 없이 API 실패 시 빈 리스트를 반환한다."""
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("fail")):
        provider = HttpFxProvider(fallback_on_error=False)
        rates = provider.get_all_rates("USD")
    assert rates == []


def test_convert():
    """환율 변환이 올바르게 계산된다."""
    data = {"result": "success", "rates": {"KRW": 1350.0}}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(data)):
        provider = HttpFxProvider(fallback_on_error=False)
        result = provider.convert(Decimal("10.0"), "USD", "KRW")
    assert result == Decimal("13500.0")


def test_is_configured_false(monkeypatch: pytest.MonkeyPatch):
    """EXCHANGE_RATE_API_KEY 미설정 시 False를 반환한다."""
    monkeypatch.delenv("EXCHANGE_RATE_API_KEY", raising=False)
    assert HttpFxProvider.is_configured() is False


def test_is_configured_true(monkeypatch: pytest.MonkeyPatch):
    """EXCHANGE_RATE_API_KEY 설정 시 True를 반환한다."""
    monkeypatch.setenv("EXCHANGE_RATE_API_KEY", "test-key-123")
    assert HttpFxProvider.is_configured() is True


def test_api_key_used_in_url():
    """API 키가 있으면 URL에 포함된다."""
    data = {"result": "success", "rates": {"EUR": 0.92}}
    captured_urls: list[str] = []

    def fake_urlopen(req: object, timeout: int = 10) -> object:
        captured_urls.append(req.full_url)  # type: ignore[union-attr]
        return _mock_urlopen(data)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        provider = HttpFxProvider(api_key="my-key-abc")
        provider.get_rate("USD", "EUR")

    assert any("apikey=my-key-abc" in url for url in captured_urls)
