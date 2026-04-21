"""FxProvider Protocol — 환율 조회 추상화."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass
class FxRate:
    """단일 환율 레코드."""

    base_currency: str    # "USD"
    target_currency: str  # "EUR", "KRW", ...
    rate: Decimal         # 1 USD = rate target_currency
    effective_date: date
    source: str           # "static" | "api"


class FxProvider(Protocol):
    """환율 조회 프로토콜."""

    name: str

    def get_rate(self, base: str, target: str, as_of: date | None = None) -> Decimal:
        """1 base 통화를 target 통화로 변환하는 환율을 반환한다."""
        ...

    def get_all_rates(self, base: str = "USD") -> list[FxRate]:
        """base 통화 기준 모든 환율 레코드를 반환한다."""
        ...
