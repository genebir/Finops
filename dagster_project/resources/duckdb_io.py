"""PostgreSQL 커넥션 매니저 Dagster 리소스.

DuckDB에서 PostgreSQL로 마이그레이션됨. 클래스명은 하위 호환성을 위해 DuckDBResource 유지.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import psycopg2
import psycopg2.extensions
from dagster import ConfigurableResource

from ..config import load_config

_cfg = load_config()


class DuckDBResource(ConfigurableResource):
    """PostgreSQL 커넥션을 Dagster 리소스로 래핑.

    기존 asset 코드와의 호환성을 위해 클래스명 유지.
    """

    db_path: str = "data/marts.duckdb"

    @contextmanager
    def get_connection(self) -> Generator[psycopg2.extensions.connection]:
        conn = psycopg2.connect(_cfg.postgres.dsn)
        conn.autocommit = True
        try:
            yield conn
        finally:
            conn.close()

    def execute(
        self, sql: str, params: list[object] | None = None
    ) -> list[tuple[object, ...]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or [])
                if cur.description:
                    return cur.fetchall()
                return []
