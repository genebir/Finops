-- anomaly_scores: Z-score 기반 이상치 탐지 결과 테이블
-- anomaly_detection asset에서 Python으로 계산한 결과를 적재한다.
CREATE TABLE IF NOT EXISTS anomaly_scores (
    resource_id       VARCHAR NOT NULL,
    cost_unit_key     VARCHAR NOT NULL,
    team              VARCHAR NOT NULL,
    product           VARCHAR NOT NULL,
    env               VARCHAR NOT NULL,
    charge_date       DATE    NOT NULL,
    effective_cost    DECIMAL(18, 6) NOT NULL,
    mean_cost         DECIMAL(18, 6) NOT NULL,
    std_cost          DECIMAL(18, 6) NOT NULL,
    z_score           DOUBLE PRECISION NOT NULL,
    is_anomaly        BOOLEAN NOT NULL,
    severity          VARCHAR NOT NULL  -- 'critical' | 'warning' | 'ok'
);
