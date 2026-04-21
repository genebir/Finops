CREATE OR REPLACE TABLE fact_daily_cost AS
SELECT
    CAST(strftime(ChargePeriodStart, '%Y-%m-%d') AS DATE) AS charge_date,
    ResourceId                                             AS resource_id,
    ResourceName                                           AS resource_name,
    ResourceType                                           AS resource_type,
    ServiceName                                            AS service_name,
    ServiceCategory                                        AS service_category,
    RegionId                                               AS region_id,
    team,
    product,
    env,
    cost_unit_key,
    SUM(CAST(EffectiveCost AS DECIMAL(18, 6)))             AS effective_cost,
    SUM(CAST(BilledCost AS DECIMAL(18, 6)))                AS billed_cost,
    SUM(CAST(ListCost AS DECIMAL(18, 6)))                  AS list_cost,
    COUNT(*)                                               AS record_count
FROM silver_focus
GROUP BY
    charge_date,
    resource_id,
    resource_name,
    resource_type,
    service_name,
    service_category,
    region_id,
    team,
    product,
    env,
    cost_unit_key
ORDER BY charge_date, effective_cost DESC;
