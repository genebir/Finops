CREATE OR REPLACE VIEW v_top_resources_30d AS
SELECT
    resource_id,
    resource_name,
    resource_type,
    service_name,
    service_category,
    region_id,
    cost_unit_key,
    team,
    product,
    env,
    SUM(effective_cost) AS total_effective_cost,
    SUM(billed_cost)    AS total_billed_cost,
    COUNT(DISTINCT charge_date) AS active_days
FROM fact_daily_cost
WHERE charge_date >= CURRENT_DATE - INTERVAL '{{lookback_days}} days'
GROUP BY
    resource_id,
    resource_name,
    resource_type,
    service_name,
    service_category,
    region_id,
    cost_unit_key,
    team,
    product,
    env
ORDER BY total_effective_cost DESC
LIMIT {{top_resources_limit}};
