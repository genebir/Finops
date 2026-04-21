"""CostRecommendationAsset 단위 테스트."""

from __future__ import annotations

import psycopg2
import pytest

from dagster_project.config import load_config

_cfg = load_config()


def _get_conn() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(_cfg.postgres.dsn)
    conn.autocommit = True
    return conn


def _ensure_tables(conn: psycopg2.extensions.connection) -> None:
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fact_daily_cost (
            provider VARCHAR NOT NULL DEFAULT 'aws',
            charge_date DATE NOT NULL,
            resource_id VARCHAR NOT NULL,
            resource_name VARCHAR,
            resource_type VARCHAR,
            service_name VARCHAR,
            service_category VARCHAR,
            region_id VARCHAR,
            team VARCHAR NOT NULL,
            product VARCHAR NOT NULL,
            env VARCHAR NOT NULL,
            cost_unit_key VARCHAR NOT NULL,
            effective_cost DECIMAL(18,6) NOT NULL,
            billed_cost DECIMAL(18,6) NOT NULL,
            list_cost DECIMAL(18,6) NOT NULL,
            record_count BIGINT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dim_cost_recommendations (
            billing_month VARCHAR,
            resource_id VARCHAR,
            team VARCHAR,
            product VARCHAR,
            env VARCHAR,
            provider VARCHAR,
            recommendation_type VARCHAR,
            reason VARCHAR,
            estimated_savings DECIMAL(18,6),
            severity VARCHAR
        )
    """)
    cur.close()


def _seed_db(conn: psycopg2.extensions.connection, month_str: str = "2024-01") -> None:
    cur = conn.cursor()
    _ensure_tables(conn)
    cur.execute("DELETE FROM fact_daily_cost WHERE resource_id LIKE 'test_res_%%'")
    cur.execute("DELETE FROM dim_cost_recommendations WHERE resource_id LIKE 'test_res_%%'")

    year, month = month_str.split("-")
    for day in range(1, 8):
        cur.execute(
            "INSERT INTO fact_daily_cost (provider, charge_date, resource_id, resource_name, "
            "service_name, team, product, env, cost_unit_key, effective_cost, billed_cost, "
            "list_cost, record_count) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                "aws", f"{year}-{month}-{day:02d}",
                "test_res_idle", "test_res_idle",
                "EC2", "test_team_a", "test_prod_x", "prod",
                "test_team_a:test_prod_x:prod", 100.0, 100.0, 100.0, 1,
            ],
        )

    prev_month = int(month) - 1
    prev_year = int(year)
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    for day in range(1, 16):
        cur.execute(
            "INSERT INTO fact_daily_cost (provider, charge_date, resource_id, resource_name, "
            "service_name, team, product, env, cost_unit_key, effective_cost, billed_cost, "
            "list_cost, record_count) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                "aws", f"{prev_year}-{prev_month:02d}-{day:02d}",
                "test_res_growth", "test_res_growth",
                "RDS", "test_team_b", "test_prod_y", "staging",
                "test_team_b:test_prod_y:staging", 50.0, 50.0, 50.0, 1,
            ],
        )
    for day in range(1, 16):
        cur.execute(
            "INSERT INTO fact_daily_cost (provider, charge_date, resource_id, resource_name, "
            "service_name, team, product, env, cost_unit_key, effective_cost, billed_cost, "
            "list_cost, record_count) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                "aws", f"{year}-{month}-{day:02d}",
                "test_res_growth", "test_res_growth",
                "RDS", "test_team_b", "test_prod_y", "staging",
                "test_team_b:test_prod_y:staging", 200.0, 200.0, 200.0, 1,
            ],
        )
    cur.close()


def _cleanup(conn: psycopg2.extensions.connection) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM fact_daily_cost WHERE resource_id LIKE 'test_res_%%'")
    cur.execute("DELETE FROM dim_cost_recommendations WHERE resource_id LIKE 'test_res_%%'")
    cur.execute("DELETE FROM anomaly_scores WHERE resource_id LIKE 'test_res_%%'")
    cur.close()


def test_high_growth_resource_detected() -> None:
    """전월 대비 200% 증가 리소스가 high_growth 추천으로 탐지된다."""
    from dagster import build_asset_context

    from dagster_project.assets.cost_recommendations import cost_recommendations
    from dagster_project.resources.duckdb_io import DuckDBResource
    from dagster_project.resources.settings_store import SettingsStoreResource

    conn = _get_conn()
    try:
        _seed_db(conn, "2024-02")

        duckdb_res = DuckDBResource()
        settings_res = SettingsStoreResource()
        settings_res.ensure_table()

        ctx = build_asset_context(partition_key="2024-02-01")
        cost_recommendations(context=ctx, duckdb_resource=duckdb_res, settings_store=settings_res)

        cur = conn.cursor()
        cur.execute(
            "SELECT recommendation_type, severity FROM dim_cost_recommendations "
            "WHERE billing_month='2024-02' AND resource_id LIKE 'test_res_%%'"
        )
        rows = cur.fetchall()
        cur.close()

        rec_types = {r[0] for r in rows}
        assert "high_growth" in rec_types
    finally:
        _cleanup(conn)
        conn.close()


def test_idempotent() -> None:
    """2회 실행해도 동일한 결과를 반환한다."""
    from dagster import build_asset_context

    from dagster_project.assets.cost_recommendations import cost_recommendations
    from dagster_project.resources.duckdb_io import DuckDBResource
    from dagster_project.resources.settings_store import SettingsStoreResource

    conn = _get_conn()
    try:
        _seed_db(conn, "2024-02")

        duckdb_res = DuckDBResource()
        settings_res = SettingsStoreResource()
        settings_res.ensure_table()

        ctx = build_asset_context(partition_key="2024-02-01")
        cost_recommendations(context=ctx, duckdb_resource=duckdb_res, settings_store=settings_res)

        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM dim_cost_recommendations WHERE billing_month='2024-02'"
        )
        count1 = cur.fetchone()[0]
        cur.close()

        cost_recommendations(context=ctx, duckdb_resource=duckdb_res, settings_store=settings_res)

        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM dim_cost_recommendations WHERE billing_month='2024-02'"
        )
        count2 = cur.fetchone()[0]
        cur.close()

        assert count1 == count2
    finally:
        _cleanup(conn)
        conn.close()


def test_persistent_anomaly_detected() -> None:
    """anomaly_scores에 3회 이상 이상치가 있는 리소스가 persistent_anomaly로 탐지된다."""
    from dagster import build_asset_context

    from dagster_project.assets.cost_recommendations import cost_recommendations
    from dagster_project.resources.duckdb_io import DuckDBResource
    from dagster_project.resources.settings_store import SettingsStoreResource

    conn = _get_conn()
    try:
        _seed_db(conn, "2024-01")

        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_scores (
                resource_id VARCHAR, cost_unit_key VARCHAR,
                team VARCHAR, product VARCHAR, env VARCHAR,
                charge_date DATE, effective_cost DECIMAL(18,6),
                mean_cost DECIMAL(18,6), std_cost DECIMAL(18,6),
                z_score DOUBLE PRECISION, is_anomaly BOOLEAN,
                severity VARCHAR, detector_name VARCHAR
            )
        """)
        for day in [5, 10, 15, 20]:
            cur.execute(
                "INSERT INTO anomaly_scores VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [
                    "test_res_idle", "test_team_a:test_prod_x:prod",
                    "test_team_a", "test_prod_x", "prod",
                    f"2024-01-{day:02d}", 500.0, 100.0, 50.0, 8.0, True, "critical", "zscore",
                ],
            )
        cur.close()

        duckdb_res = DuckDBResource()
        settings_res = SettingsStoreResource()
        settings_res.ensure_table()

        ctx = build_asset_context(partition_key="2024-01-01")
        cost_recommendations(context=ctx, duckdb_resource=duckdb_res, settings_store=settings_res)

        cur = conn.cursor()
        cur.execute(
            "SELECT recommendation_type FROM dim_cost_recommendations "
            "WHERE billing_month='2024-01' AND resource_id LIKE 'test_res_%%'"
        )
        rows = cur.fetchall()
        cur.close()

        rec_types = {r[0] for r in rows}
        assert "persistent_anomaly" in rec_types
    finally:
        _cleanup(conn)
        conn.close()
