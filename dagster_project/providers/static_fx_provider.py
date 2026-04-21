"""StaticFxProvider — 설정 파일 기반 정적 환율 제공자."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..core.fx_provider import FxRate

# 기본 정적 환율 (USD 기준)
_DEFAULT_RATES: dict[str, Decimal] = {
    "USD": Decimal("1.0"),
    "EUR": Decimal("0.92"),
    "GBP": Decimal("0.79"),
    "KRW": Decimal("1350.0"),
    "JPY": Decimal("149.5"),
    "CNY": Decimal("7.24"),
    "SGD": Decimal("1.34"),
    "AUD": Decimal("1.53"),
}


class StaticFxProvider:
    """정적 환율 표로 환율을 제공한다.

    실제 API 연동 없이 설정된 환율로 통화 변환을 지원한다.
    Phase 6에서 실시간 API 제공자로 교체 가능하다.
    """

    name: str = "static"

    def __init__(self, rates: dict[str, Decimal] | None = None) -> None:
        self._rates: dict[str, Decimal] = rates if rates is not None else dict(_DEFAULT_RATES)

    def get_rate(self, base: str, target: str, as_of: date | None = None) -> Decimal:
        """1 base 단위를 target 통화로 환산하는 환율을 반환한다.

        Args:
            base: 기준 통화 (예: "USD")
            target: 목표 통화 (예: "KRW")
            as_of: 환율 기준일 (StaticProvider는 무시)

        Returns:
            환율 Decimal. base == target이면 1.0 반환.

        Raises:
            KeyError: base 또는 target 통화가 지원되지 않을 때.
        """
        if base == target:
            return Decimal("1.0")

        base_usd = self._rates.get(base)
        target_usd = self._rates.get(target)

        if base_usd is None:
            raise KeyError(f"Unsupported base currency: {base}")
        if target_usd is None:
            raise KeyError(f"Unsupported target currency: {target}")

        # base → USD → target
        return target_usd / base_usd

    def get_all_rates(self, base: str = "USD") -> list[FxRate]:
        """base 통화 기준 전체 환율 목록을 반환한다."""
        today = date.today()
        base_usd = self._rates.get(base)
        if base_usd is None:
            raise KeyError(f"Unsupported base currency: {base}")

        return [
            FxRate(
                base_currency=base,
                target_currency=target,
                rate=rate / base_usd,
                effective_date=today,
                source="static",
            )
            for target, rate in self._rates.items()
        ]

    def convert(self, amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
        """금액을 from_currency에서 to_currency로 변환한다."""
        rate = self.get_rate(from_currency, to_currency)
        return amount * rate
