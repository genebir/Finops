"""ConsoleSink — 로컬 개발/테스트용 콘솔 알림 구현체."""

from __future__ import annotations

import logging

from ..core.alert_sink import Alert

logger = logging.getLogger(__name__)


class ConsoleSink:
    """알림을 표준 로그로 출력한다. 로컬 테스트 및 기본 fallback용."""

    name: str = "console"

    def send(self, alert: Alert) -> None:
        level = logging.CRITICAL if alert.severity == "critical" else (
            logging.WARNING if alert.severity == "warning" else logging.INFO
        )
        logger.log(
            level,
            "[%s][%s] %s | actual=%.4f ref=%.4f deviation=%.1f%%",
            alert.alert_type.upper(),
            alert.severity.upper(),
            alert.message,
            float(alert.actual_cost),
            float(alert.reference_cost),
            alert.deviation_pct,
        )

    def send_batch(self, alerts: list[Alert]) -> None:
        for alert in alerts:
            self.send(alert)
