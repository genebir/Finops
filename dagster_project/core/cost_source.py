"""CostSource Protocol — 비용 데이터 소스 추상 인터페이스."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Protocol

from ..schemas.focus_v1 import FocusRecord


class CostSource(Protocol):
    """FOCUS 1.0 규격 비용 레코드를 생성하는 소스 인터페이스.

    Phase 1 구현체: AwsCurGenerator (가상)
    Phase 3 예정: GcpBillingExport, AzureCostExport
    """

    name: str  # "aws" | "gcp" | "azure"
    resource_id_strategy: str  # "terraform_address" | "arn" | "native"

    def generate(self, period_start: date, period_end: date) -> Iterable[FocusRecord]:
        """지정된 기간의 FOCUS 규격 비용 레코드를 yield."""
        ...
