"""DuckDB 커넥션 매니저 Dagster 리소스."""

from __future__ import annotations

import random
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import duckdb
from dagster import ConfigurableResource

_MAX_RETRIES = 12
_BASE_DELAY = 0.5  # seconds


class DuckDBResource(ConfigurableResource):
    """DuckDB 파일 커넥션을 Dagster 리소스로 래핑."""

    db_path: str = "data/marts.duckdb"

    @contextmanager
    def get_connection(self) -> Generator[duckdb.DuckDBPyConnection]:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                conn = duckdb.connect(self.db_path)
                try:
                    yield conn
                finally:
                    conn.close()
                return
            except duckdb.IOException as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    delay = _BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                    time.sleep(delay)
        raise last_exc  # type: ignore[misc]

    def execute(self, sql: str, params: list[object] | None = None) -> duckdb.DuckDBPyRelation:
        with self.get_connection() as conn:
            return conn.execute(sql, params or [])  # type: ignore[return-value]
