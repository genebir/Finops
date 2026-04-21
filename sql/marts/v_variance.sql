-- Infracost 예측 vs 실제 비용 편차 계산
-- dim_forecast LEFT JOIN fact_daily_cost (월 집계)
CREATE OR REPLACE VIEW v_variance AS
WITH actual_mtd AS (
    SELECT
        resource_id,
        DATE_TRUNC('month', charge_date) AS billing_month,
        SUM(effective_cost)              AS actual_mtd
    FROM fact_daily_cost
    GROUP BY resource_id, DATE_TRUNC('month', charge_date)
)
SELECT
    f.resource_address                                          AS resource_id,
    f.monthly_cost                                              AS forecast_monthly,
    COALESCE(a.actual_mtd, 0)                                   AS actual_mtd,
    COALESCE(a.actual_mtd, 0) - f.monthly_cost                  AS variance_abs,
    CASE
        WHEN f.monthly_cost = 0 THEN NULL
        ELSE (COALESCE(a.actual_mtd, 0) - f.monthly_cost)
             / f.monthly_cost * 100
    END                                                          AS variance_pct,
    CASE
        WHEN a.resource_id IS NULL                               THEN 'unmatched'
        WHEN (COALESCE(a.actual_mtd, 0) - f.monthly_cost)
             / NULLIF(f.monthly_cost, 0) * 100 > 20             THEN 'over'
        WHEN (COALESCE(a.actual_mtd, 0) - f.monthly_cost)
             / NULLIF(f.monthly_cost, 0) * 100 < -20            THEN 'under'
        ELSE 'ok'
    END                                                          AS status,
    f.currency,
    f.forecast_generated_at,
    a.billing_month
FROM dim_forecast f
LEFT JOIN actual_mtd a ON f.resource_address = a.resource_id;
