"""Central PostgreSQL schema bootstrap.

모든 기반 테이블을 한 곳에서 CREATE IF NOT EXISTS로 관리한다.
- 신규 환경(fresh DB)에서 `scripts/init_db.py` 또는 `ensure_base_tables()`를 호출하면
  마트 파이프라인이 바로 실행될 수 있는 상태가 된다.
- 각 asset은 쓰기 전에 `ensure_base_tables(conn)`을 호출해 자기 부트스트랩한다.
"""

from __future__ import annotations

import logging

import psycopg2.extensions

log = logging.getLogger(__name__)


BASE_TABLE_DDL: dict[str, str] = {
    # Gold 마트 — 멀티 클라우드 통합 팩트
    "fact_daily_cost": """
        CREATE TABLE IF NOT EXISTS fact_daily_cost (
            provider         VARCHAR        NOT NULL DEFAULT 'aws',
            charge_date      DATE           NOT NULL,
            resource_id      VARCHAR        NOT NULL,
            resource_name    VARCHAR,
            resource_type    VARCHAR,
            service_name     VARCHAR,
            service_category VARCHAR,
            region_id        VARCHAR,
            team             VARCHAR        NOT NULL,
            product          VARCHAR        NOT NULL,
            env              VARCHAR        NOT NULL,
            cost_unit_key    VARCHAR        NOT NULL,
            effective_cost   DECIMAL(18, 6) NOT NULL,
            billed_cost      DECIMAL(18, 6) NOT NULL,
            list_cost        DECIMAL(18, 6) NOT NULL,
            record_count     BIGINT         NOT NULL
        )
    """,
    "dim_cost_unit": """
        CREATE TABLE IF NOT EXISTS dim_cost_unit (
            cost_unit_key   VARCHAR NOT NULL,
            team            VARCHAR NOT NULL,
            product         VARCHAR NOT NULL,
            env             VARCHAR NOT NULL,
            resource_count  BIGINT  NOT NULL
        )
    """,
    # 이상치 탐지
    "anomaly_scores": """
        CREATE TABLE IF NOT EXISTS anomaly_scores (
            resource_id       VARCHAR          NOT NULL,
            cost_unit_key     VARCHAR          NOT NULL,
            team              VARCHAR          NOT NULL,
            product           VARCHAR          NOT NULL,
            env               VARCHAR          NOT NULL,
            charge_date       DATE             NOT NULL,
            effective_cost    DECIMAL(18, 6)   NOT NULL,
            mean_cost         DECIMAL(18, 6)   NOT NULL,
            std_cost          DECIMAL(18, 6)   NOT NULL,
            z_score           DOUBLE PRECISION NOT NULL,
            is_anomaly        BOOLEAN          NOT NULL,
            severity          VARCHAR          NOT NULL,
            detector_name     VARCHAR          NOT NULL DEFAULT 'zscore'
        )
    """,
    # 예측
    "dim_forecast": """
        CREATE TABLE IF NOT EXISTS dim_forecast (
            resource_address       VARCHAR          NOT NULL,
            monthly_cost           DECIMAL(18, 6)   NOT NULL,
            hourly_cost            DECIMAL(18, 6)   NOT NULL,
            currency               VARCHAR          NOT NULL,
            forecast_generated_at  TIMESTAMPTZ      NOT NULL
        )
    """,
    "dim_prophet_forecast": """
        CREATE TABLE IF NOT EXISTS dim_prophet_forecast (
            resource_id                VARCHAR          NOT NULL,
            predicted_monthly_cost     DOUBLE PRECISION NOT NULL,
            lower_bound_monthly_cost   DOUBLE PRECISION NOT NULL,
            upper_bound_monthly_cost   DOUBLE PRECISION NOT NULL,
            hourly_cost                DOUBLE PRECISION NOT NULL,
            currency                   VARCHAR          NOT NULL,
            model_trained_at           VARCHAR          NOT NULL
        )
    """,
    "dim_forecast_variance_prophet": """
        CREATE TABLE IF NOT EXISTS dim_forecast_variance_prophet (
            resource_id                VARCHAR          NOT NULL,
            billing_month              VARCHAR          NOT NULL,
            predicted_monthly_cost     DOUBLE PRECISION NOT NULL,
            lower_bound_monthly_cost   DOUBLE PRECISION NOT NULL,
            upper_bound_monthly_cost   DOUBLE PRECISION NOT NULL,
            actual_monthly_cost        DOUBLE PRECISION NOT NULL,
            variance_abs               DOUBLE PRECISION NOT NULL,
            variance_pct               DOUBLE PRECISION,
            status                     VARCHAR          NOT NULL
        )
    """,
    # 예산 / Chargeback
    "dim_budget": """
        CREATE TABLE IF NOT EXISTS dim_budget (
            team           VARCHAR        NOT NULL,
            env            VARCHAR        NOT NULL,
            budget_amount  DECIMAL(18, 6) NOT NULL,
            billing_month  VARCHAR        NOT NULL DEFAULT 'default',
            updated_at     TIMESTAMPTZ    DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (team, env, billing_month)
        )
    """,
    "dim_budget_status": """
        CREATE TABLE IF NOT EXISTS dim_budget_status (
            billing_month    VARCHAR          NOT NULL,
            team             VARCHAR          NOT NULL,
            env              VARCHAR          NOT NULL,
            budget_amount    DECIMAL(18, 6)   NOT NULL,
            actual_cost      DOUBLE PRECISION NOT NULL,
            utilization_pct  DOUBLE PRECISION NOT NULL,
            status           VARCHAR          NOT NULL
        )
    """,
    "dim_chargeback": """
        CREATE TABLE IF NOT EXISTS dim_chargeback (
            billing_month    VARCHAR          NOT NULL,
            provider         VARCHAR          NOT NULL,
            team             VARCHAR          NOT NULL,
            product          VARCHAR          NOT NULL,
            env              VARCHAR          NOT NULL,
            cost_unit_key    VARCHAR          NOT NULL,
            actual_cost      DOUBLE PRECISION NOT NULL,
            budget_amount    DECIMAL(18, 6),
            utilization_pct  DOUBLE PRECISION,
            resource_count   BIGINT           NOT NULL
        )
    """,
    # FX / Recommendations
    "dim_fx_rates": """
        CREATE TABLE IF NOT EXISTS dim_fx_rates (
            base_currency    VARCHAR          NOT NULL,
            target_currency  VARCHAR          NOT NULL,
            rate             DOUBLE PRECISION NOT NULL,
            effective_date   VARCHAR          NOT NULL,
            source           VARCHAR          NOT NULL
        )
    """,
    "dim_cost_recommendations": """
        CREATE TABLE IF NOT EXISTS dim_cost_recommendations (
            billing_month        VARCHAR        NOT NULL,
            resource_id          VARCHAR        NOT NULL,
            team                 VARCHAR        NOT NULL,
            product              VARCHAR        NOT NULL,
            env                  VARCHAR        NOT NULL,
            provider             VARCHAR        NOT NULL,
            recommendation_type  VARCHAR        NOT NULL,
            reason               VARCHAR        NOT NULL,
            estimated_savings    DECIMAL(18, 6),
            severity             VARCHAR        NOT NULL
        )
    """,
    # Showback 리포트 (Phase 18)
    "dim_showback_report": """
        CREATE TABLE IF NOT EXISTS dim_showback_report (
            id              BIGSERIAL        PRIMARY KEY,
            billing_month   VARCHAR          NOT NULL,
            team            VARCHAR          NOT NULL,
            total_cost      DOUBLE PRECISION NOT NULL,
            budget_amount   DOUBLE PRECISION,
            utilization_pct DOUBLE PRECISION,
            anomaly_count   INTEGER          NOT NULL DEFAULT 0,
            top_services    JSONB,
            top_resources   JSONB,
            generated_at    TIMESTAMPTZ      NOT NULL
        )
    """,
    # 비용 배분 (Phase 17)
    "dim_allocation_rules": """
        CREATE TABLE IF NOT EXISTS dim_allocation_rules (
            id           BIGSERIAL        PRIMARY KEY,
            resource_id  VARCHAR          NOT NULL,
            team         VARCHAR          NOT NULL,
            split_pct    DOUBLE PRECISION NOT NULL,
            description  VARCHAR,
            created_at   TIMESTAMPTZ      NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT allocation_pct_range CHECK (split_pct > 0 AND split_pct <= 100)
        )
    """,
    "dim_allocated_cost": """
        CREATE TABLE IF NOT EXISTS dim_allocated_cost (
            id              BIGSERIAL        PRIMARY KEY,
            charge_date     DATE             NOT NULL,
            resource_id     VARCHAR          NOT NULL,
            resource_name   VARCHAR,
            resource_type   VARCHAR,
            service_name    VARCHAR,
            provider        VARCHAR          NOT NULL,
            original_team   VARCHAR          NOT NULL,
            allocated_team  VARCHAR          NOT NULL,
            split_pct       DOUBLE PRECISION NOT NULL,
            original_cost   DOUBLE PRECISION NOT NULL,
            allocated_cost  DOUBLE PRECISION NOT NULL,
            env             VARCHAR,
            cost_unit_key   VARCHAR,
            allocation_type VARCHAR          NOT NULL,
            computed_at     TIMESTAMPTZ      NOT NULL
        )
    """,
    # 태그 정책 위반 (Phase 16)
    "dim_tag_violations": """
        CREATE TABLE IF NOT EXISTS dim_tag_violations (
            id               BIGSERIAL        PRIMARY KEY,
            resource_id      VARCHAR          NOT NULL,
            resource_type    VARCHAR,
            service_category VARCHAR,
            provider         VARCHAR          NOT NULL,
            team             VARCHAR,
            env              VARCHAR,
            violation_type   VARCHAR          NOT NULL,
            missing_tag      VARCHAR          NOT NULL,
            severity         VARCHAR          NOT NULL,
            cost_30d         DOUBLE PRECISION,
            detected_at      TIMESTAMPTZ      NOT NULL
        )
    """,
    # 리소스 인벤토리 (Phase 15)
    "dim_resource_inventory": """
        CREATE TABLE IF NOT EXISTS dim_resource_inventory (
            resource_id        VARCHAR          NOT NULL PRIMARY KEY,
            resource_name      VARCHAR,
            resource_type      VARCHAR,
            service_name       VARCHAR,
            service_category   VARCHAR,
            region_id          VARCHAR,
            provider           VARCHAR          NOT NULL,
            team               VARCHAR,
            product            VARCHAR,
            env                VARCHAR,
            cost_unit_key      VARCHAR,
            first_seen_date    DATE             NOT NULL,
            last_seen_date     DATE             NOT NULL,
            total_cost_30d     DOUBLE PRECISION NOT NULL DEFAULT 0,
            tags_complete      BOOLEAN          NOT NULL,
            missing_tags       VARCHAR,
            refreshed_at       TIMESTAMPTZ      NOT NULL
        )
    """,
    # 번 레이트 (Phase 14)
    "dim_burn_rate": """
        CREATE TABLE IF NOT EXISTS dim_burn_rate (
            billing_month         VARCHAR          NOT NULL,
            team                  VARCHAR          NOT NULL,
            env                   VARCHAR          NOT NULL,
            days_elapsed          INTEGER          NOT NULL,
            days_in_month         INTEGER          NOT NULL,
            mtd_cost              DOUBLE PRECISION NOT NULL,
            daily_avg             DOUBLE PRECISION NOT NULL,
            projected_eom         DOUBLE PRECISION NOT NULL,
            budget_amount         DOUBLE PRECISION,
            projected_utilization DOUBLE PRECISION,
            status                VARCHAR          NOT NULL,
            refreshed_at          TIMESTAMPTZ      NOT NULL
        )
    """,
    # 데이터 품질 (Phase 13)
    "dim_data_quality": """
        CREATE TABLE IF NOT EXISTS dim_data_quality (
            id              BIGSERIAL        PRIMARY KEY,
            checked_at      TIMESTAMPTZ      NOT NULL,
            table_name      VARCHAR          NOT NULL,
            column_name     VARCHAR          NOT NULL,
            check_type      VARCHAR          NOT NULL,
            row_count       BIGINT,
            failed_count    BIGINT,
            null_ratio      DOUBLE PRECISION,
            passed          BOOLEAN          NOT NULL,
            detail          TEXT
        )
    """,
    # 운영 로그(Phase 12)
    "pipeline_run_log": """
        CREATE TABLE IF NOT EXISTS pipeline_run_log (
            id            BIGSERIAL       PRIMARY KEY,
            run_id        VARCHAR         NOT NULL,
            asset_key     VARCHAR         NOT NULL,
            partition_key VARCHAR,
            status        VARCHAR         NOT NULL,
            started_at    TIMESTAMPTZ     NOT NULL,
            finished_at   TIMESTAMPTZ,
            duration_sec  DOUBLE PRECISION,
            row_count     BIGINT,
            error_message TEXT
        )
    """,
}


def ensure_base_tables(conn: psycopg2.extensions.connection) -> None:
    """모든 기반 테이블을 CREATE IF NOT EXISTS로 생성한다 (멱등)."""
    cur = conn.cursor()
    try:
        for name, ddl in BASE_TABLE_DDL.items():
            cur.execute(ddl)
            log.debug("ensured table %s", name)
    finally:
        cur.close()


def ensure_tables(conn: psycopg2.extensions.connection, *names: str) -> None:
    """지정된 테이블만 CREATE IF NOT EXISTS."""
    cur = conn.cursor()
    try:
        for name in names:
            ddl = BASE_TABLE_DDL.get(name)
            if ddl is None:
                raise KeyError(f"unknown base table: {name}")
            cur.execute(ddl)
    finally:
        cur.close()
