"""PostgreSQL 스키마 부트스트랩 CLI.

install.sh 또는 초기 배포 시점에 한 번 실행하여 모든 기반 테이블을 만든다.
이후에는 각 asset이 자기 쓰기 경로에서 ensure_tables()로 자기 부트스트랩도 하므로,
이 스크립트는 있으면 편하고 없어도 파이프라인은 돌아간다.

Usage:
    uv run python scripts/init_db.py
"""

from __future__ import annotations

import sys

import psycopg2

from dagster_project.config import load_config
from dagster_project.db_schema import BASE_TABLE_DDL, ensure_base_tables
from dagster_project.resources.budget_store import BudgetStoreResource
from dagster_project.resources.settings_store import SettingsStoreResource


def main() -> int:
    cfg = load_config()
    dsn = cfg.postgres.dsn
    print(f"[init_db] connecting to {cfg.postgres.host}:{cfg.postgres.port}/{cfg.postgres.dbname} ...")
    try:
        conn = psycopg2.connect(dsn)
    except psycopg2.OperationalError as e:
        print(f"[init_db] ERROR — PostgreSQL 연결 실패: {e}", file=sys.stderr)
        return 1

    conn.autocommit = True
    try:
        ensure_base_tables(conn)
        print(f"[init_db] ensured {len(BASE_TABLE_DDL)} base tables:")
        for name in BASE_TABLE_DDL:
            print(f"         - {name}")

        # settings/budget resources seed defaults
        SettingsStoreResource().ensure_table()
        print("[init_db] platform_settings seeded with default thresholds")

        BudgetStoreResource().ensure_table()
        print("[init_db] dim_budget ready")

        # Report current row counts
        cur = conn.cursor()
        print("\n[init_db] current row counts:")
        for table in BASE_TABLE_DDL:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                (count,) = cur.fetchone()
                print(f"         {table:35s} {count:>8d}")
            except psycopg2.Error as err:
                print(f"         {table:35s} (error: {err})")
                conn.rollback()
        cur.close()
    finally:
        conn.close()

    print("\n[init_db] 완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
