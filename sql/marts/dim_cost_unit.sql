CREATE OR REPLACE TABLE dim_cost_unit AS
SELECT DISTINCT
    cost_unit_key,
    team,
    product,
    env,
    COUNT(DISTINCT resource_id) AS resource_count
FROM fact_daily_cost
GROUP BY cost_unit_key, team, product, env
ORDER BY cost_unit_key;
