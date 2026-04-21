"""EmailSink — SMTP 기반 이메일 AlertSink 구현체."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..core.alert_sink import Alert

logger = logging.getLogger(__name__)

_ENV_SMTP_HOST = "SMTP_HOST"
_ENV_SMTP_PORT = "SMTP_PORT"
_ENV_SMTP_USER = "SMTP_USER"
_ENV_SMTP_PASSWORD = "SMTP_PASSWORD"
_ENV_ALERT_FROM = "ALERT_EMAIL_FROM"
_ENV_ALERT_TO = "ALERT_EMAIL_TO"


class EmailSink:
    """SMTP를 통해 이메일로 Alert를 발송하는 AlertSink 구현체.

    환경변수:
        SMTP_HOST: SMTP 서버 주소 (기본: localhost)
        SMTP_PORT: SMTP 포트 (기본: 587)
        SMTP_USER: SMTP 인증 사용자명
        SMTP_PASSWORD: SMTP 인증 비밀번호
        ALERT_EMAIL_FROM: 발신자 이메일
        ALERT_EMAIL_TO: 수신자 이메일 (쉼표로 여러 개 지정 가능)
    """

    name: str = "email"

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        from_addr: str | None = None,
        to_addrs: list[str] | None = None,
    ) -> None:
        self._smtp_host = smtp_host or os.environ.get(_ENV_SMTP_HOST, "localhost")
        self._smtp_port = smtp_port or int(os.environ.get(_ENV_SMTP_PORT, "587"))
        self._smtp_user = smtp_user or os.environ.get(_ENV_SMTP_USER, "")
        self._smtp_password = smtp_password or os.environ.get(_ENV_SMTP_PASSWORD, "")
        self._from_addr = from_addr or os.environ.get(_ENV_ALERT_FROM, "finops@example.com")

        if to_addrs is not None:
            self._to_addrs = to_addrs
        else:
            to_env = os.environ.get(_ENV_ALERT_TO, "")
            self._to_addrs = [addr.strip() for addr in to_env.split(",") if addr.strip()]

    @classmethod
    def is_configured(cls) -> bool:
        """ALERT_EMAIL_TO 환경변수가 설정되어 있으면 True를 반환한다."""
        return bool(os.environ.get(_ENV_ALERT_TO, "").strip())

    def send(self, alert: Alert) -> None:
        """단일 Alert를 이메일로 발송한다."""
        self.send_batch([alert])

    def send_batch(self, alerts: list[Alert]) -> None:
        """여러 Alert를 단일 이메일로 묶어 발송한다."""
        if not alerts:
            return
        if not self._to_addrs:
            logger.warning("EmailSink: ALERT_EMAIL_TO 미설정 — 이메일 발송 건너뜀")
            return

        subject = f"[FinOps Alert] {len(alerts)}개 알림 ({alerts[0].severity} 포함)"
        body = self._build_body(alerts)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from_addr
        msg["To"] = ", ".join(self._to_addrs)
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=10) as server:
                server.ehlo()
                if self._smtp_user and self._smtp_password:
                    server.starttls()
                    server.login(self._smtp_user, self._smtp_password)
                server.sendmail(self._from_addr, self._to_addrs, msg.as_string())
            logger.info(f"EmailSink: {len(alerts)}개 alert 발송 완료 → {self._to_addrs}")
        except OSError as exc:
            logger.error(f"EmailSink: 이메일 발송 실패 — {exc}")
            raise

    def _build_body(self, alerts: list[Alert]) -> str:
        lines = [
            "FinOps Platform Alert Summary",
            "=" * 40,
            f"Total alerts: {len(alerts)}",
            "",
        ]
        for i, alert in enumerate(alerts, start=1):
            lines += [
                f"[{i}] {alert.alert_type.upper()} | {alert.severity.upper()}",
                f"    Resource: {alert.resource_id}",
                f"    Cost Unit: {alert.cost_unit_key}",
                f"    Message: {alert.message}",
                f"    Actual: ${float(alert.actual_cost):.2f} | "
                f"Reference: ${float(alert.reference_cost):.2f} | "
                f"Deviation: {alert.deviation_pct:+.1f}%",
                f"    Triggered: {alert.triggered_at.isoformat()}",
                "",
            ]
        return "\n".join(lines)
