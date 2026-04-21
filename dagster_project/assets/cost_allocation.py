"""Cost Allocation Asset — splits shared resource costs across teams by configured rules."""

import datetime

import psycopg2.extras
from dagster import AssetExecutionContext, asset

from ..resources.duckdb_io import DuckDBResource

_RULES_DDL = """
CREATE TABLE IF NOT EXISTS dim_allocation_rules (
    id           BIGSERIAL       PRIMARY KEY,
    resource_id  VARCHAR         NOT NULL,
    team         VARCHAR         NOT NULL,
    split_pct    DOUBLE PRECISION NOT NULL,
    description  VARCHAR,
    created_at   TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT allocation_pct_range CHECK (split_pct > 0 AND split_pct <= 100)
)
"""

_ALLOCATED_DDL = """
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
"""


def _fetch_rules(conn) -> dict[str, list[tuple[str, float]]]:
    """Return {resource_id: [(team, pct), ...]}."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='dim_allocation_rules'"
        )
        if cur.fetchone() is None:
            return {}
        cur.execute("SELECT resource_id, team, split_pct FROM dim_allocation_rules ORDER BY resource_id, team")
        rows = cur.fetchall()

    rules: dict[str, list[tuple[str, float]]] = {}
    for resource_id, team, pct in rows:
        rules.setdefault(resource_id, []).append((team, pct))
    return rules


@asset(
    deps=["gold_marts", "gold_marts_gcp", "gold_marts_azure"],
    description=(
        "Applies cost allocation split rules from dim_allocation_rules to fact_daily_cost, "
        "producing attributed team costs in dim_allocated_cost."
    ),
    group_name="reporting",
)
def cost_allocation(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
) -> None:
    """Split shared resource costs across teams per allocation rules."""
    now = datetime.datetime.now(datetime.UTC)

    with duckdb_resource.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_RULES_DDL)
            cur.execute(_ALLOCATED_DDL)

        rules = _fetch_rules(conn)
        if not rules:
            context.log.info("cost_allocation: no allocation rules configured — skipping")
            return

        resource_ids = list(rules.keys())
        placeholders = ",".join(["%s"] * len(resource_ids))

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT charge_date, resource_id, resource_name, resource_type,
                       service_name, provider, team, env, cost_unit_key,
                       CAST(SUM(effective_cost) AS DOUBLE PRECISION) AS total_cost
                FROM fact_daily_cost
                WHERE resource_id IN ({placeholders})
                GROUP BY charge_date, resource_id, resource_name, resource_type,
                         service_name, provider, team, env, cost_unit_key
                """,  # noqa: S608
                resource_ids,
            )
            cols = [d[0] for d in cur.description]
            source_rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        records: list[tuple] = []
        for row in source_rows:
            rid = row["resource_id"]
            splits = rules[rid]
            total_pct = sum(p for _, p in splits)

            for alloc_team, pct in splits:
                allocated = row["total_cost"] * (pct / 100.0)
                records.append((
                    row["charge_date"], rid, row.get("resource_name"), row.get("resource_type"),
                    row.get("service_name"), row["provider"], row["team"], alloc_team,
                    pct, row["total_cost"], allocated,
                    row.get("env"), row.get("cost_unit_key"),
                    "split" if total_pct < 99.9 or len(splits) > 1 else "full",
                    now,
                ))

        with conn.cursor() as cur:
            cur.execute("DELETE FROM dim_allocated_cost WHERE resource_id = ANY(%s)", (resource_ids,))
            if records:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO dim_allocated_cost
                      (charge_date, resource_id, resource_name, resource_type,
                       service_name, provider, original_team, allocated_team,
                       split_pct, original_cost, allocated_cost,
                       env, cost_unit_key, allocation_type, computed_at)
                    VALUES %s
                    """,
                    records,
                )

    context.log.info(
        "cost_allocation: %d records written for %d resources",
        len(records), len(resource_ids),
    )
