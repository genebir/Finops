-- PostgreSQL: DELETE + INSERT pattern (CREATE OR REPLACE TABLE not supported)
DELETE FROM dim_cost_unit;
INSERT INTO dim_cost_unit (cost_unit_key, team, product, env, resource_count)
SELECT DISTINCT
    cost_unit_key,
    team,
    product,
    env,
    COUNT(DISTINCT resource_id) AS resource_count
FROM fact_daily_cost
GROUP BY cost_unit_key, team, product, env
ORDER BY cost_unit_key;
