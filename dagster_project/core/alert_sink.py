"""AlertSink Protocol — 알림 발송 추상 인터페이스."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass
class Alert:
    """단일 알림 이벤트."""

    alert_type: str       # "anomaly" | "variance_over" | "variance_under"
    severity: str         # "info" | "warning" | "critical"
    resource_id: str
    cost_unit_key: str
    message: str
    actual_cost: Decimal
    reference_cost: Decimal  # 예측값(variance) 또는 평균(anomaly)
    deviation_pct: float
    triggered_at: datetime
    extra: dict[str, object] = field(default_factory=dict)


class AlertSink(Protocol):
    """알림을 외부 채널로 발송하는 인터페이스.

    Phase 2 구현체: ConsoleSink, SlackSink
    Phase 3 예정: PagerDutySink, EmailSink
    """

    name: str

    def send(self, alert: Alert) -> None:
        """단일 알림을 발송한다."""
        ...

    def send_batch(self, alerts: list[Alert]) -> None:
        """다수의 알림을 일괄 발송한다."""
        ...
