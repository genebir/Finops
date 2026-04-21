"""BudgetStoreResource — DuckDB dim_budget 테이블 기반 예산 관리.

예산은 (team, env) 키로 관리한다.
team="*" 또는 env="*" 와일드카드로 범용 예산을 설정할 수 있다.
조회 우선순위: 정확히 일치 → team 와일드카드 → env 와일드카드 → 전체 와일드카드
"""

from __future__ import annotations

from pathlib import Path

import duckdb
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
    """DuckDB dim_budget 테이블에서 예산 데이터를 읽고 쓴다.

    기본 예산은 settings.yaml의 budget_defaults.entries에서 seed된다.
    이미 존재하는 (team, env, 'default') 항목은 덮어쓰지 않는다.
    """

    db_path: str = "data/marts.duckdb"

    def _connect(self) -> duckdb.DuckDBPyConnection:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(self.db_path)

    def ensure_table(self) -> None:
        """테이블이 없으면 생성하고 settings.yaml의 기본값을 seed한다."""
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE_SQL)
            for entry in _cfg.budget_defaults.entries:
                conn.execute(
                    """
                    INSERT INTO dim_budget (team, env, budget_amount, billing_month)
                    VALUES (?, ?, ?, 'default')
                    ON CONFLICT (team, env, billing_month) DO NOTHING
                    """,
                    [entry.team, entry.env, entry.amount],
                )

    def get_budget(self, team: str, env: str, billing_month: str = "default") -> float | None:
        """(team, env) 쌍의 예산을 조회한다.

        우선순위: 정확 일치 > team=* > env=* > *,* 와일드카드.
        billing_month 지정 시 해당 월 예산을 먼저 찾고, 없으면 'default'로 폴백.
        """
        # 우선순위: 정확 일치 > team 특정(env=*) > env 특정(team=*) > 전체 와일드카드
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
            with self._connect() as conn:
                for t, e, m in candidates:
                    row = conn.execute(
                        "SELECT budget_amount FROM dim_budget WHERE team=? AND env=? AND billing_month=?",
                        [t, e, m],
                    ).fetchone()
                    if row:
                        return float(row[0])
        except Exception:  # noqa: BLE001
            pass
        return None

    def all_budgets(self, billing_month: str = "default") -> list[dict[str, object]]:
        """지정된 billing_month의 모든 예산 항목을 반환한다."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT team, env, budget_amount, billing_month, updated_at "
                    "FROM dim_budget WHERE billing_month=? ORDER BY team, env",
                    [billing_month],
                ).fetchall()
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
        except Exception:  # noqa: BLE001
            return []

    def upsert_budget(
        self, team: str, env: str, amount: float, billing_month: str = "default"
    ) -> None:
        """예산 항목을 삽입하거나 업데이트한다."""
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE_SQL)
            existing = conn.execute(
                "SELECT team FROM dim_budget WHERE team=? AND env=? AND billing_month=?",
                [team, env, billing_month],
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE dim_budget SET budget_amount=?, updated_at=NOW() "
                    "WHERE team=? AND env=? AND billing_month=?",
                    [amount, team, env, billing_month],
                )
            else:
                conn.execute(
                    "INSERT INTO dim_budget (team, env, budget_amount, billing_month) VALUES (?, ?, ?, ?)",
                    [team, env, amount, billing_month],
                )
