"""HttpFxProvider — HTTP API 기반 실시간 환율 제공자.

환경변수 EXCHANGE_RATE_API_KEY 설정 시 open.er-api.com으로 실시간 환율을 조회한다.
미설정이거나 API 호출 실패 시 StaticFxProvider로 자동 폴백한다.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import date
from decimal import Decimal

from ..core.fx_provider import FxRate
from .static_fx_provider import StaticFxProvider

logger = logging.getLogger(__name__)

_ENV_API_KEY = "EXCHANGE_RATE_API_KEY"
_API_BASE = "https://open.er-api.com/v6/latest"
_DEFAULT_TIMEOUT = 10


class HttpFxProvider:
    """HTTP API로 실시간 환율을 가져오는 FxProvider 구현체.

    open.er-api.com 무료 API를 사용한다. API 키가 없어도 동작하지만,
    요청 한도 초과 시 StaticFxProvider로 폴백한다.

    환경변수:
        EXCHANGE_RATE_API_KEY: API 인증 키 (선택; 미설정 시 익명 엔드포인트 사용)
    """

    name: str = "http"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
        fallback_on_error: bool = True,
    ) -> None:
        self._api_key = api_key or os.environ.get(_ENV_API_KEY, "")
        self._timeout = timeout
        self._fallback = StaticFxProvider() if fallback_on_error else None
        self._cache: dict[str, dict[str, Decimal]] | None = None

    @classmethod
    def is_configured(cls) -> bool:
        """EXCHANGE_RATE_API_KEY 환경변수가 설정되어 있으면 True."""
        return bool(os.environ.get(_ENV_API_KEY, "").strip())

    def _fetch_rates(self, base: str) -> dict[str, Decimal]:
        """API에서 환율을 가져온다. 실패 시 빈 dict 반환."""
        if self._api_key:
            url = f"{_API_BASE}/{base}?apikey={self._api_key}"
        else:
            url = f"{_API_BASE}/{base}"

        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data: dict[str, object] = json.loads(resp.read().decode())
            if data.get("result") != "success":
                logger.warning(f"HttpFxProvider: API error — {data.get('error-type')}")
                return {}
            raw_rates = data.get("rates", {})
            return {k: Decimal(str(v)) for k, v in raw_rates.items()}  # type: ignore[union-attr]
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            logger.warning(f"HttpFxProvider: 환율 조회 실패 ({exc}) — fallback 사용")
            return {}

    def get_rate(self, base: str, target: str, as_of: date | None = None) -> Decimal:
        """1 base 단위의 target 환율을 반환한다.

        API 호출 실패 시 StaticFxProvider로 폴백한다.
        """
        if base == target:
            return Decimal("1.0")

        rates = self._fetch_rates(base)
        if rates and target in rates:
            return rates[target]

        if self._fallback:
            logger.info(f"HttpFxProvider: {base}/{target} 폴백 → StaticFxProvider")
            return self._fallback.get_rate(base, target)

        raise KeyError(f"환율 조회 실패: {base}/{target}")

    def get_all_rates(self, base: str = "USD") -> list[FxRate]:
        """base 통화 기준 전체 환율 목록을 반환한다."""
        today = date.today()
        rates = self._fetch_rates(base)

        if not rates:
            if self._fallback:
                logger.info(f"HttpFxProvider: 전체 환율 폴백 → StaticFxProvider (base={base})")
                return self._fallback.get_all_rates(base)
            return []

        return [
            FxRate(
                base_currency=base,
                target_currency=target,
                rate=rate,
                effective_date=today,
                source="http",
            )
            for target, rate in rates.items()
        ]

    def convert(self, amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
        """금액을 from_currency에서 to_currency로 변환한다."""
        rate = self.get_rate(from_currency, to_currency)
        return amount * rate
