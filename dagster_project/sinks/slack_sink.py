"""SlackSink — Slack Incoming Webhook 알림 구현체."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from ..config import load_config
from ..core.alert_sink import Alert

_SEVERITY_EMOJI: dict[str, str] = {
    "critical": ":red_circle:",
    "warning": ":large_yellow_circle:",
    "info": ":large_blue_circle:",
}


class SlackSink:
    """Slack Incoming Webhook으로 알림을 발송한다.

    SLACK_WEBHOOK_URL 환경변수가 없으면 send() 호출 시 RuntimeError를 발생시킨다.
    환경변수 존재 여부는 사용 전 `is_configured()` 로 확인한다.
    """

    name: str = "slack"

    def __init__(self, webhook_url: str | None = None) -> None:
        self._webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")
        self._timeout = load_config().slack.webhook_timeout_sec

    @classmethod
    def is_configured(cls) -> bool:
        return bool(os.environ.get("SLACK_WEBHOOK_URL"))

    def _build_payload(self, alert: Alert) -> dict[str, object]:
        emoji = _SEVERITY_EMOJI.get(alert.severity, ":bell:")
        return {
            "text": f"{emoji} *FinOps Alert* [{alert.alert_type.upper()}] {alert.message}",
            "attachments": [
                {
                    "color": "#ff0000" if alert.severity == "critical" else "#ffaa00",
                    "fields": [
                        {"title": "Resource", "value": alert.resource_id, "short": True},
                        {"title": "Cost Unit", "value": alert.cost_unit_key, "short": True},
                        {
                            "title": "Actual Cost",
                            "value": f"${float(alert.actual_cost):.4f}",
                            "short": True,
                        },
                        {
                            "title": "Reference Cost",
                            "value": f"${float(alert.reference_cost):.4f}",
                            "short": True,
                        },
                        {
                            "title": "Deviation",
                            "value": f"{alert.deviation_pct:+.1f}%",
                            "short": True,
                        },
                        {
                            "title": "Triggered At",
                            "value": alert.triggered_at.isoformat(),
                            "short": True,
                        },
                    ],
                }
            ],
        }

    def send(self, alert: Alert) -> None:
        if not self._webhook_url:
            raise RuntimeError(
                "SLACK_WEBHOOK_URL이 설정되지 않았습니다. "
                "SlackSink.is_configured()로 확인 후 사용하세요."
            )
        payload = self._build_payload(alert)
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Slack webhook 응답 오류: {resp.status}")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Slack webhook 전송 실패: {exc}") from exc

    def send_batch(self, alerts: list[Alert]) -> None:
        for alert in alerts:
            self.send(alert)
