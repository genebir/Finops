"""BudgetStoreResource — PostgreSQL dim_budget 테이블 기반 예산 관리.

예산은 (team, env) 키로 관리한다.
team="*" 또는 env="*" 와일드카드로 범용 예산을 설정할 수 있다.
조회 우선순위: 정확히 일치 → team 와일드카드 → env 와일드카드 → 전체 와일드카드
"""

from __future__ import annotations

import psycopg2
import psycopg2.extensions
from dagster import ConfigurableResource

from ..config import BudgetEntryConfig, load_config

_cfg = load_config()

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dim_budget (
    team           VARCHAR NOT NULL,
    env            VARCHAR NOT NULL,
    budget_amount  DECIMAL(18, 6) NOT NULL,
    billing_month  VARCHAR NOT NULL DEFAULT 'default',
    updated_at     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (team, env, billing_month)
)
"""


class BudgetStoreResource(ConfigurableResource):  # type: ignore[type-arg]
    """PostgreSQL dim_budget 테이블에서 예산 데이터를 읽고 쓴다."""

    db_path: str = "data/marts.duckdb"

    def _connect(self) -> psycopg2.extensions.connection:
        conn = psycopg2.connect(_cfg.postgres.dsn)
        conn.autocommit = True
        return conn

    def ensure_table(self) -> None:
        """테이블이 없으면 생성하고 settings.yaml의 기본값을 seed한다."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(_CREATE_TABLE_SQL)
                for entry in _cfg.budget_defaults.entries:
                    cur.execute(
                        """
                        INSERT INTO dim_budget (team, env, budget_amount, billing_month)
                        VALUES (%s, %s, %s, 'default')
                        ON CONFLICT (team, env, billing_month) DO NOTHING
                        """,
                        [entry.team, entry.env, entry.amount],
                    )
        finally:
            conn.close()

    def get_budget(self, team: str, env: str, billing_month: str = "default") -> float | None:
        """(team, env) 쌍의 예산을 조회한다."""
        candidates = [
            (team, env, billing_month),
            (team, env, "default"),
            (team, "*", billing_month),
            (team, "*", "default"),
            ("*", env, billing_month),
            ("*", env, "default"),
            ("*", "*", billing_month),
            ("*", "*", "default"),
        ]
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    for t, e, m in candidates:
                        cur.execute(
                            "SELECT budget_amount FROM dim_budget WHERE team=%s AND env=%s AND billing_month=%s",
                            [t, e, m],
                        )
                        row = cur.fetchone()
                        if row:
                            return float(row[0])
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            pass
        return None

    def all_budgets(self, billing_month: str = "default") -> list[dict[str, object]]:
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT team, env, budget_amount, billing_month, updated_at "
                        "FROM dim_budget WHERE billing_month=%s ORDER BY team, env",
                        [billing_month],
                    )
                    rows = cur.fetchall()
                return [
                    {
                        "team": r[0],
                        "env": r[1],
                        "budget_amount": float(r[2]),
                        "billing_month": r[3],
                        "updated_at": r[4],
                    }
                    for r in rows
                ]
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            return []

    def upsert_budget(
        self, team: str, env: str, amount: float, billing_month: str = "default"
    ) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(_CREATE_TABLE_SQL)
                cur.execute(
                    "SELECT team FROM dim_budget WHERE team=%s AND env=%s AND billing_month=%s",
                    [team, env, billing_month],
                )
                if cur.fetchone():
                    cur.execute(
                        "UPDATE dim_budget SET budget_amount=%s, updated_at=NOW() "
                        "WHERE team=%s AND env=%s AND billing_month=%s",
                        [amount, team, env, billing_month],
                    )
                else:
                    cur.execute(
                        "INSERT INTO dim_budget (team, env, budget_amount, billing_month) VALUES (%s, %s, %s, %s)",
                        [team, env, amount, billing_month],
                    )
        finally:
            conn.close()
