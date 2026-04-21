"""EmailSink 단위 테스트 — SMTP mocking 기반."""

from __future__ import annotations

import smtplib
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from dagster_project.core.alert_sink import Alert
from dagster_project.sinks.email_sink import EmailSink


def _make_alert(severity: str = "warning") -> Alert:
    return Alert(
        alert_type="anomaly",
        severity=severity,
        resource_id="aws_instance.web_1",
        cost_unit_key="platform:web:prod",
        message="Test alert",
        actual_cost=Decimal("500.0"),
        reference_cost=Decimal("100.0"),
        deviation_pct=400.0,
        triggered_at=datetime.now(tz=UTC),
    )


class TestEmailSink:
    def test_is_configured_false_without_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ALERT_EMAIL_TO", raising=False)
        assert EmailSink.is_configured() is False

    def test_is_configured_true_with_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALERT_EMAIL_TO", "ops@example.com")
        assert EmailSink.is_configured() is True

    def test_send_empty_batch_does_nothing(self) -> None:
        sink = EmailSink(to_addrs=["ops@example.com"])
        sink.send_batch([])  # 예외 없이 완료

    def test_send_batch_no_to_addrs_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ALERT_EMAIL_TO", raising=False)
        sink = EmailSink()
        sink.send_batch([_make_alert()])  # ALERT_EMAIL_TO 미설정 → 경고만 로깅

    def test_send_calls_send_batch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sent: list[list[Alert]] = []

        def fake_send_batch(alerts: list[Alert]) -> None:
            sent.append(alerts)

        sink = EmailSink(to_addrs=["ops@example.com"])
        monkeypatch.setattr(sink, "send_batch", fake_send_batch)
        sink.send(_make_alert())
        assert len(sent) == 1
        assert len(sent[0]) == 1

    def test_send_batch_raises_on_smtp_error(self) -> None:
        def fake_smtp(*args: object, **kwargs: object) -> smtplib.SMTP:
            raise OSError("Connection refused")

        sink = EmailSink(to_addrs=["ops@example.com"])
        alert = _make_alert()

        with pytest.raises(OSError, match="Connection refused"):
            # SMTPlib를 직접 패치하지 않고 SMTP 생성자 실패를 시뮬레이션
            import smtplib as smtp_module
            original = smtp_module.SMTP

            class FailingSMTP:
                def __init__(self, *a: object, **k: object) -> None:
                    raise OSError("Connection refused")

            smtp_module.SMTP = FailingSMTP  # type: ignore[assignment]
            try:
                sink.send_batch([alert])
            finally:
                smtp_module.SMTP = original  # type: ignore[assignment]

    def test_build_body_contains_alert_info(self) -> None:
        sink = EmailSink(to_addrs=["ops@example.com"])
        alert = _make_alert("critical")
        body = sink._build_body([alert])
        assert "aws_instance.web_1" in body
        assert "platform:web:prod" in body
        assert "critical" in body.lower() or "ANOMALY" in body

    def test_init_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
        monkeypatch.setenv("SMTP_PORT", "465")
        monkeypatch.setenv("SMTP_USER", "user@test.com")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")
        monkeypatch.setenv("ALERT_EMAIL_FROM", "finops@test.com")
        monkeypatch.setenv("ALERT_EMAIL_TO", "ops@test.com,sre@test.com")
        sink = EmailSink()
        assert sink._smtp_host == "smtp.test.com"
        assert sink._smtp_port == 465
        assert len(sink._to_addrs) == 2
        assert sink.name == "email"

    def test_multiple_recipients_in_build_body(self) -> None:
        sink = EmailSink(to_addrs=["a@b.com", "c@d.com"])
        alerts = [_make_alert("warning"), _make_alert("critical")]
        body = sink._build_body(alerts)
        assert "Total alerts: 2" in body
