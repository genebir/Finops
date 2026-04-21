"""Tag Policy Asset — evaluates resources against configurable tag policy rules."""

import datetime
import json

import psycopg2.extras
from dagster import AssetExecutionContext, asset

from ..resources.duckdb_io import DuckDBResource
from ..resources.settings_store import SettingsStoreResource

_POLICY_DDL = """
CREATE TABLE IF NOT EXISTS dim_tag_violations (
    id                  BIGSERIAL        PRIMARY KEY,
    resource_id         VARCHAR          NOT NULL,
    resource_type       VARCHAR,
    service_category    VARCHAR,
    provider            VARCHAR          NOT NULL,
    team                VARCHAR,
    env                 VARCHAR,
    violation_type      VARCHAR          NOT NULL,
    missing_tag         VARCHAR          NOT NULL,
    severity            VARCHAR          NOT NULL,
    cost_30d            DOUBLE PRECISION,
    detected_at         TIMESTAMPTZ      NOT NULL
)
"""

# Default policy: all resources must have team + env; Compute also needs product
_DEFAULT_POLICY: dict[str, list[str]] = {
    "*":        ["team", "env"],
    "Compute":  ["team", "env", "product"],
    "Database": ["team", "env", "product"],
    "Storage":  ["team", "env"],
    "Network":  ["team", "env"],
}


def _load_policy(settings_store: SettingsStoreResource) -> dict[str, list[str]]:
    raw = settings_store.get_str("tag_policy.rules", "")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return _DEFAULT_POLICY


def _severity(missing_count: int, cost_30d: float) -> str:
    if cost_30d > 1000 or missing_count >= 2:
        return "critical"
    return "warning"


@asset(
    deps=["resource_inventory"],
    description=(
        "Evaluates dim_resource_inventory against configurable tag policy rules "
        "and stores violations in dim_tag_violations."
    ),
    group_name="reporting",
)
def tag_policy(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
    settings_store: SettingsStoreResource,
) -> None:
    """Run tag policy check against all known resources."""
    settings_store.ensure_table()
    policy = _load_policy(settings_store)
    now = datetime.datetime.now(datetime.UTC)

    with duckdb_resource.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_POLICY_DDL)

        # Fetch inventory
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT resource_id, resource_type, service_category, provider,
                       team, env, product, total_cost_30d
                FROM dim_resource_inventory
                """
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        violations: list[dict] = []
        for r in rows:
            category = r.get("service_category") or "*"
            required = list(policy.get(category, policy.get("*", [])))
            # Add wildcard rules too
            if category != "*":
                for t in policy.get("*", []):
                    if t not in required:
                        required.append(t)

            for tag in required:
                val = r.get(tag)
                if not val or val in ("unknown", ""):
                    violations.append({
                        "resource_id": r["resource_id"],
                        "resource_type": r.get("resource_type"),
                        "service_category": r.get("service_category"),
                        "provider": r["provider"],
                        "team": r.get("team"),
                        "env": r.get("env"),
                        "violation_type": "missing_required_tag",
                        "missing_tag": tag,
                        "severity": _severity(1, r.get("total_cost_30d") or 0.0),
                        "cost_30d": r.get("total_cost_30d"),
                        "detected_at": now,
                    })

        # Replace today's violations
        with conn.cursor() as cur:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            cur.execute("DELETE FROM dim_tag_violations WHERE detected_at >= %s", (today_start,))

            if violations:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO dim_tag_violations
                      (resource_id, resource_type, service_category, provider,
                       team, env, violation_type, missing_tag, severity,
                       cost_30d, detected_at)
                    VALUES %s
                    """,
                    [
                        (
                            v["resource_id"], v["resource_type"], v["service_category"],
                            v["provider"], v["team"], v["env"],
                            v["violation_type"], v["missing_tag"], v["severity"],
                            v["cost_30d"], v["detected_at"],
                        )
                        for v in violations
                    ],
                )

    critical = sum(1 for v in violations if v["severity"] == "critical")
    context.log.info(
        "tag_policy: %d violations (%d critical) across %d resources",
        len(violations), critical, len(rows),
    )
