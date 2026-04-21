"""Resource Inventory Asset — unified catalog of all resources with tag completeness."""

import datetime

import psycopg2.extras
from dagster import AssetExecutionContext, asset

from ..db_schema import ensure_tables
from ..resources.duckdb_io import DuckDBResource

_MANDATORY_TAGS = ("team", "product", "env")

_INV_DDL = """
CREATE TABLE IF NOT EXISTS dim_resource_inventory (
    resource_id        VARCHAR          NOT NULL,
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
"""

_UPSERT_SQL = """
INSERT INTO dim_resource_inventory
  (resource_id, resource_name, resource_type, service_name, service_category,
   region_id, provider, team, product, env, cost_unit_key,
   first_seen_date, last_seen_date, total_cost_30d,
   tags_complete, missing_tags, refreshed_at)
VALUES %s
ON CONFLICT (resource_id)
DO UPDATE SET
  resource_name    = EXCLUDED.resource_name,
  resource_type    = EXCLUDED.resource_type,
  service_name     = EXCLUDED.service_name,
  service_category = EXCLUDED.service_category,
  region_id        = EXCLUDED.region_id,
  provider         = EXCLUDED.provider,
  team             = EXCLUDED.team,
  product          = EXCLUDED.product,
  env              = EXCLUDED.env,
  cost_unit_key    = EXCLUDED.cost_unit_key,
  last_seen_date   = EXCLUDED.last_seen_date,
  total_cost_30d   = EXCLUDED.total_cost_30d,
  tags_complete    = EXCLUDED.tags_complete,
  missing_tags     = EXCLUDED.missing_tags,
  refreshed_at     = EXCLUDED.refreshed_at
"""

_UPSERT_DDL_WITH_PK = """
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
"""


@asset(
    deps=["gold_marts", "gold_marts_gcp", "gold_marts_azure"],
    description=(
        "Builds a unified resource inventory from fact_daily_cost, "
        "tracking tag completeness (team/product/env) per resource."
    ),
    group_name="reporting",
)
def resource_inventory(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
) -> None:
    """Upsert resource inventory with tag completeness check."""
    now = datetime.datetime.now(datetime.UTC)
    cutoff_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()

    with duckdb_resource.get_connection() as conn:
        ensure_tables(conn, "pipeline_run_log")

        with conn.cursor() as cur:
            cur.execute(_UPSERT_DDL_WITH_PK)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    resource_id,
                    MAX(resource_name)      AS resource_name,
                    MAX(resource_type)      AS resource_type,
                    MAX(service_name)       AS service_name,
                    MAX(service_category)   AS service_category,
                    MAX(region_id)          AS region_id,
                    MAX(provider)           AS provider,
                    MAX(team)               AS team,
                    MAX(product)            AS product,
                    MAX(env)                AS env,
                    MAX(cost_unit_key)      AS cost_unit_key,
                    MIN(charge_date)        AS first_seen_date,
                    MAX(charge_date)        AS last_seen_date,
                    CAST(
                        SUM(CASE WHEN charge_date >= %s THEN effective_cost ELSE 0 END)
                        AS DOUBLE PRECISION
                    ) AS total_cost_30d
                FROM fact_daily_cost
                GROUP BY resource_id
                """,
                (cutoff_date,),
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]

        records = []
        for row in rows:
            r = dict(zip(cols, row))
            missing = [
                tag for tag in _MANDATORY_TAGS
                if not r.get(tag) or r[tag] in ("unknown", "", None)
            ]
            r["tags_complete"] = len(missing) == 0
            r["missing_tags"] = ",".join(missing) if missing else None
            r["refreshed_at"] = now
            records.append(r)

        if records:
            with conn.cursor() as cur2:
                psycopg2.extras.execute_values(
                    cur2,
                    _UPSERT_SQL,
                    [
                        (
                            rec["resource_id"], rec["resource_name"], rec["resource_type"],
                            rec["service_name"], rec["service_category"], rec["region_id"],
                            rec["provider"], rec["team"], rec["product"], rec["env"],
                            rec["cost_unit_key"], rec["first_seen_date"], rec["last_seen_date"],
                            rec["total_cost_30d"], rec["tags_complete"], rec["missing_tags"],
                            rec["refreshed_at"],
                        )
                        for rec in records
                    ],
                )

    incomplete = sum(1 for r in records if not r["tags_complete"])
    context.log.info(
        "resource_inventory: %d resources — %d tag-complete, %d incomplete",
        len(records), len(records) - incomplete, incomplete,
    )
