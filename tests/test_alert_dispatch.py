"""AlertSink 및 Alert 생성 로직 테스트."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from dagster_project.core.alert_sink import Alert
from dagster_project.sinks.console_sink import ConsoleSink
from dagster_project.sinks.slack_sink import SlackSink


def _make_alert(
    alert_type: str = "anomaly",
    severity: str = "critical",
    deviation_pct: float = 150.0,
) -> Alert:
    return Alert(
        alert_type=alert_type,
        severity=severity,
        resource_id="aws_instance.web_1",
        cost_unit_key="platform:checkout:prod",
        message="Test alert",
        actual_cost=Decimal("150.000000"),
        reference_cost=Decimal("60.000000"),
        deviation_pct=deviation_pct,
        triggered_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
    )


class TestAlertDataclass:
    def test_alert_fields(self) -> None:
        alert = _make_alert()
        assert alert.alert_type == "anomaly"
        assert alert.severity == "critical"
        assert alert.resource_id == "aws_instance.web_1"
        assert isinstance(alert.actual_cost, Decimal)
        assert isinstance(alert.reference_cost, Decimal)
        assert alert.extra == {}

    def test_alert_with_extra(self) -> None:
        alert = _make_alert()
        alert.extra["z_score"] = 4.5
        assert alert.extra["z_score"] == 4.5


class TestConsoleSink:
    def test_send_does_not_raise(self) -> None:
        sink = ConsoleSink()
        alert = _make_alert(severity="critical")
        sink.send(alert)  # 예외 없이 실행되어야 함

    def test_send_batch_does_not_raise(self) -> None:
        sink = ConsoleSink()
        alerts = [
            _make_alert("anomaly", "critical"),
            _make_alert("variance_over", "warning", 30.0),
            _make_alert("variance_under", "info", -25.0),
        ]
        sink.send_batch(alerts)

    def test_send_empty_batch(self) -> None:
        sink = ConsoleSink()
        sink.send_batch([])  # 빈 배치도 정상 처리

    def test_console_sink_name(self) -> None:
        sink = ConsoleSink()
        assert sink.name == "console"


class TestSlackSink:
    def test_slack_sink_name(self) -> None:
        sink = SlackSink(webhook_url="https://hooks.slack.com/test")
        assert sink.name == "slack"

    def test_send_without_url_raises(self) -> None:
        sink = SlackSink(webhook_url="")
        with pytest.raises(RuntimeError, match="SLACK_WEBHOOK_URL"):
            sink.send(_make_alert())

    def test_is_configured_false_when_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        assert SlackSink.is_configured() is False

    def test_is_configured_true_when_env_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
        assert SlackSink.is_configured() is True

    def test_build_payload_structure(self) -> None:
        sink = SlackSink(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert(severity="critical")
        payload = sink._build_payload(alert)
        assert "text" in payload
        assert "attachments" in payload
        assert payload["attachments"][0]["color"] == "#ff0000"  # type: ignore[index]

    def test_build_payload_warning_color(self) -> None:
        sink = SlackSink(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert(severity="warning")
        payload = sink._build_payload(alert)
        assert payload["attachments"][0]["color"] == "#ffaa00"  # type: ignore[index]

    def test_send_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import MagicMock, patch

        sink = SlackSink(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            sink.send(alert)

    def test_send_http_error_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.error
        from unittest.mock import patch

        sink = SlackSink(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert()

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with pytest.raises(RuntimeError, match="전송 실패"):
                sink.send(alert)

    def test_send_batch_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import MagicMock, patch

        sink = SlackSink(webhook_url="https://hooks.slack.com/test")
        alerts = [_make_alert("anomaly", "critical"), _make_alert("variance_over", "warning", 30.0)]

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            sink.send_batch(alerts)
            assert mock_open.call_count == 2
