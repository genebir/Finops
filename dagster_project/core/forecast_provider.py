"""ForecastProvider Protocol — 비용 예측 소스 추상 인터페이스."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass
class ForecastScope:
    """예측 범위 파라미터."""

    terraform_path: str
    as_of: datetime | None = None


@dataclass
class ForecastRecord:
    """단일 리소스 예측 레코드."""

    resource_address: str
    monthly_cost: Decimal
    hourly_cost: Decimal
    currency: str
    forecast_generated_at: datetime
    lower_bound_monthly_cost: Decimal = Decimal("0")
    upper_bound_monthly_cost: Decimal = Decimal("0")


class ForecastProvider(Protocol):
    """비용 예측을 제공하는 소스 인터페이스.

    Phase 1 구현체: InfracostProvider
    Phase 2 예정: ProphetProvider (시계열 기반)
    """

    name: str  # "infracost" | "prophet" | "manual_budget"

    def forecast(self, scope: ForecastScope) -> list[ForecastRecord]:
        """지정된 scope에 대한 예측 레코드 목록을 반환한다."""
        ...
