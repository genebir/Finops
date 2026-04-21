-- Phase 3: provider 컬럼 추가로 멀티 클라우드 지원
-- gold_marts / gold_marts_gcp에서 파티션 키별 DELETE + INSERT로 멱등성 보장
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
);
