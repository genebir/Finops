"""SettingsStoreResource — PostgreSQL platform_settings 테이블 기반 런타임 설정 관리.

운영 중 조정이 필요한 임계값을 PostgreSQL 테이블에 저장한다.
Dagster UI를 재시작하지 않아도 값을 변경할 수 있다.

테이블 직접 수정 예시:
    UPDATE platform_settings SET value = '3.0' WHERE key = 'anomaly.zscore.warning';
"""

from __future__ import annotations

import psycopg2
import psycopg2.extensions
from dagster import ConfigurableResource

from ..config import load_config

_cfg = load_config()

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS platform_settings (
    key         VARCHAR PRIMARY KEY,
    value       VARCHAR  NOT NULL,
    value_type  VARCHAR  NOT NULL,
    description VARCHAR,
    updated_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
)
"""

_DEFAULT_SETTINGS: list[tuple[str, str, str, str]] = [
    ("anomaly.zscore.warning",          "2.0",  "float", "Z-score 경고 임계값"),
    ("anomaly.zscore.critical",         "3.0",  "float", "Z-score 위험 임계값"),
    ("variance.threshold.over_pct",     "20.0", "float", "실제 > 예측 기준 % (over 상태)"),
    ("variance.threshold.under_pct",    "20.0", "float", "예측 > 실제 기준 % (under 상태, 절대값)"),
    ("alert.critical_deviation_pct",    "50.0", "float", "이 % 이상 편차 시 critical 심각도"),
    ("alert.slack_timeout_sec",         "10",   "int",   "Slack webhook HTTP 타임아웃(초)"),
    ("reporting.lookback_days",         "30",   "int",   "Top-N 리소스 집계 기간(일)"),
    ("reporting.top_resources_limit",   "20",   "int",   "Top 리소스 뷰 최대 결과 수"),
    ("reporting.top_cost_units_limit",  "10",   "int",   "Top CostUnit 뷰 최대 결과 수"),
    ("infracost.subprocess_timeout_sec","120",  "int",   "infracost 프로세스 타임아웃(초)"),
    ("anomaly.active_detectors",        "zscore,isolation_forest", "str", "활성 탐지기 목록 (콤마 구분)"),
    ("isolation_forest.contamination",  "0.05", "float", "IsolationForest 오염 비율 (예상 이상치 비율)"),
    ("isolation_forest.n_estimators",   "100",  "int",   "IsolationForest 트리 개수"),
    ("isolation_forest.random_state",   "42",   "int",   "IsolationForest 랜덤 시드"),
    ("isolation_forest.score_critical", "-0.20","float", "anomaly score 이 값 미만 → critical"),
    ("isolation_forest.score_warning",  "-0.05","float", "anomaly score 이 값 미만 → warning"),
    ("budget.alert_threshold_pct",      "80.0", "float", "예산 사용률 이 % 이상 시 경고 알림"),
    ("budget.over_threshold_pct",       "100.0","float", "예산 사용률 이 % 이상 시 초과 알림"),
    ("moving_average.window_days",      "7",    "int",   "이동평균 윈도우 크기(일)"),
    ("moving_average.multiplier_warning",  "2.0", "float", "이동평균 경고 임계값 배수"),
    ("moving_average.multiplier_critical", "3.0", "float", "이동평균 위험 임계값 배수"),
    ("moving_average.min_window",       "3",    "int",   "이동평균 계산 최소 데이터 포인트 수"),
    ("arima.order_p",                   "1",    "int",   "ARIMA p 차수 (AR)"),
    ("arima.order_d",                   "1",    "int",   "ARIMA d 차수 (적분)"),
    ("arima.order_q",                   "1",    "int",   "ARIMA q 차수 (MA)"),
    ("arima.threshold_warning",         "2.0",  "float", "ARIMA 잔차 경고 임계값 (σ 배수)"),
    ("arima.threshold_critical",        "3.0",  "float", "ARIMA 잔차 위험 임계값 (σ 배수)"),
    ("arima.min_samples",               "10",   "int",   "ARIMA 모델 최소 샘플 수"),
    ("autoencoder.window_size",         "7",    "int",   "Autoencoder 슬라이딩 윈도우 크기"),
    ("autoencoder.threshold_warning",   "2.0",  "float", "Autoencoder 재구성 오차 경고 임계값 (σ 배수)"),
    ("autoencoder.threshold_critical",  "3.0",  "float", "Autoencoder 재구성 오차 위험 임계값 (σ 배수)"),
    ("autoencoder.min_samples",         "14",   "int",   "Autoencoder 최소 샘플 수"),
    ("autoencoder.max_iter",            "200",  "int",   "Autoencoder MLPRegressor 최대 반복 횟수"),
]


class SettingsStoreResource(ConfigurableResource):  # type: ignore[type-arg]
    """PostgreSQL platform_settings 테이블에서 런타임 설정을 읽고 쓴다."""

    def _connect(self) -> psycopg2.extensions.connection:
        conn = psycopg2.connect(_cfg.postgres.dsn)
        conn.autocommit = True
        return conn

    def ensure_table(self) -> None:
        """테이블이 없으면 생성하고 기본값을 seed한다."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(_CREATE_TABLE_SQL)
                for key, value, value_type, description in _DEFAULT_SETTINGS:
                    cur.execute(
                        """
                        INSERT INTO platform_settings (key, value, value_type, description)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (key) DO NOTHING
                        """,
                        [key, value, value_type, description],
                    )
        finally:
            conn.close()

    def get_float(self, key: str, default: float) -> float:
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT value FROM platform_settings WHERE key = %s", [key]
                    )
                    row = cur.fetchone()
                return float(row[0]) if row else default
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            return default

    def get_int(self, key: str, default: int) -> int:
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT value FROM platform_settings WHERE key = %s", [key]
                    )
                    row = cur.fetchone()
                return int(row[0]) if row else default
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            return default

    def get_str(self, key: str, default: str) -> str:
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT value FROM platform_settings WHERE key = %s", [key]
                    )
                    row = cur.fetchone()
                return str(row[0]) if row else default
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            return default

    def set_value(self, key: str, value: str) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT key FROM platform_settings WHERE key = %s", [key]
                )
                if cur.fetchone():
                    cur.execute(
                        "UPDATE platform_settings SET value = %s, updated_at = NOW() WHERE key = %s",
                        [value, key],
                    )
                else:
                    cur.execute(
                        "INSERT INTO platform_settings (key, value, value_type) VALUES (%s, %s, 'str')",
                        [key, value],
                    )
        finally:
            conn.close()

    def delete_setting(self, key: str) -> bool:
        """설정 키를 삭제한다. 삭제 성공 시 True 반환."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM platform_settings WHERE key = %s", [key]
                )
                return cur.rowcount > 0
        finally:
            conn.close()

    def all_settings(self) -> list[dict[str, object]]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT key, value, value_type, description, updated_at "
                    "FROM platform_settings ORDER BY key"
                )
                rows = cur.fetchall()
            return [
                {
                    "key": r[0],
                    "value": r[1],
                    "value_type": r[2],
                    "description": r[3],
                    "updated_at": r[4],
                }
                for r in rows
            ]
        finally:
            conn.close()
