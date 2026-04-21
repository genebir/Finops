"""Data Quality Asset — validates pipeline output after gold mart materialisation."""

import datetime

import psycopg2.extras
from dagster import AssetExecutionContext, asset

from ..db_schema import ensure_tables
from ..resources.duckdb_io import DuckDBResource

# Tables and columns to validate
_CHECKS: list[dict] = [
    # (table, column, check_type, threshold)
    {"table": "fact_daily_cost",  "column": "effective_cost", "check": "min_rows",       "threshold": 1},
    {"table": "fact_daily_cost",  "column": "effective_cost", "check": "no_negatives",   "threshold": 0},
    {"table": "fact_daily_cost",  "column": "resource_id",    "check": "null_ratio",      "threshold": 0.0},
    {"table": "fact_daily_cost",  "column": "team",           "check": "null_ratio",      "threshold": 0.0},
    {"table": "anomaly_scores",   "column": "effective_cost", "check": "no_negatives",    "threshold": 0},
    {"table": "anomaly_scores",   "column": "resource_id",    "check": "null_ratio",      "threshold": 0.0},
    {"table": "dim_prophet_forecast", "column": "predicted_monthly_cost", "check": "no_negatives", "threshold": 0},
    {"table": "dim_budget",       "column": "budget_amount",  "check": "no_negatives",    "threshold": 0},
    {"table": "dim_chargeback",   "column": "actual_cost",    "check": "no_negatives",    "threshold": 0},
    {"table": "dim_fx_rates",     "column": "rate",           "check": "no_negatives",    "threshold": 0},
]

_DIM_DQ_DDL = """
CREATE TABLE IF NOT EXISTS dim_data_quality (
    id              BIGSERIAL        PRIMARY KEY,
    checked_at      TIMESTAMPTZ      NOT NULL,
    table_name      VARCHAR          NOT NULL,
    column_name     VARCHAR          NOT NULL,
    check_type      VARCHAR          NOT NULL,
    row_count       BIGINT,
    failed_count    BIGINT,
    null_ratio      DOUBLE PRECISION,
    passed          BOOLEAN          NOT NULL,
    detail          TEXT
)
"""


def _run_checks(conn) -> list[dict]:
    results: list[dict] = []
    now = datetime.datetime.now(datetime.UTC)

    with conn.cursor() as cur:
        # Ensure dim_data_quality exists
        cur.execute(_DIM_DQ_DDL)

        for chk in _CHECKS:
            table = chk["table"]
            col = chk["column"]
            chk_type = chk["check"]
            threshold = chk["threshold"]

            # Check table exists
            cur.execute(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename=%s",
                (table,),
            )
            if cur.fetchone() is None:
                results.append({
                    "checked_at": now, "table_name": table, "column_name": col,
                    "check_type": chk_type, "row_count": None, "failed_count": None,
                    "null_ratio": None, "passed": False,
                    "detail": f"table {table!r} does not exist",
                })
                continue

            try:
                if chk_type == "min_rows":
                    cur.execute(f'SELECT COUNT(*) FROM "{table}"')  # noqa: S608
                    row_count = cur.fetchone()[0]
                    passed = row_count >= threshold
                    results.append({
                        "checked_at": now, "table_name": table, "column_name": col,
                        "check_type": chk_type, "row_count": row_count,
                        "failed_count": 0 if passed else 1, "null_ratio": None,
                        "passed": passed,
                        "detail": f"row_count={row_count} (min={threshold})",
                    })

                elif chk_type == "no_negatives":
                    cur.execute(
                        f'SELECT COUNT(*), SUM(CASE WHEN "{col}" < 0 THEN 1 ELSE 0 END) FROM "{table}"'  # noqa: S608
                    )
                    row_count, neg_count = cur.fetchone()
                    neg_count = neg_count or 0
                    passed = neg_count == 0
                    results.append({
                        "checked_at": now, "table_name": table, "column_name": col,
                        "check_type": chk_type, "row_count": row_count,
                        "failed_count": neg_count, "null_ratio": None,
                        "passed": passed,
                        "detail": f"negative_rows={neg_count}",
                    })

                elif chk_type == "null_ratio":
                    cur.execute(
                        f'SELECT COUNT(*), SUM(CASE WHEN "{col}" IS NULL THEN 1 ELSE 0 END) FROM "{table}"'  # noqa: S608
                    )
                    row_count, null_count = cur.fetchone()
                    null_count = null_count or 0
                    ratio = null_count / row_count if row_count else 0.0
                    passed = ratio <= threshold
                    results.append({
                        "checked_at": now, "table_name": table, "column_name": col,
                        "check_type": chk_type, "row_count": row_count,
                        "failed_count": null_count, "null_ratio": ratio,
                        "passed": passed,
                        "detail": f"null_ratio={ratio:.4f} (max={threshold})",
                    })

            except Exception as exc:  # noqa: BLE001
                results.append({
                    "checked_at": now, "table_name": table, "column_name": col,
                    "check_type": chk_type, "row_count": None, "failed_count": None,
                    "null_ratio": None, "passed": False,
                    "detail": f"error: {exc}",
                })

    return results


@asset(
    deps=["gold_marts", "gold_marts_gcp", "gold_marts_azure",
          "anomaly_detection", "prophet_forecast", "budget_alerts",
          "chargeback", "fx_rates"],
    description="Validates pipeline output quality and stores results in dim_data_quality.",
)
def data_quality(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
) -> None:
    """Run data quality checks and persist results to dim_data_quality."""
    with duckdb_resource.get_connection() as conn:
        ensure_tables(conn, "pipeline_run_log")

        results = _run_checks(conn)

        # Persist results — keep rolling 7-day window
        with conn.cursor() as cur:
            cur.execute(_DIM_DQ_DDL)
            cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7)
            cur.execute("DELETE FROM dim_data_quality WHERE checked_at < %s", (cutoff,))

            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO dim_data_quality
                  (checked_at, table_name, column_name, check_type,
                   row_count, failed_count, null_ratio, passed, detail)
                VALUES %s
                """,
                [
                    (
                        r["checked_at"], r["table_name"], r["column_name"],
                        r["check_type"], r["row_count"], r["failed_count"],
                        r["null_ratio"], r["passed"], r["detail"],
                    )
                    for r in results
                ],
            )

    total = len(results)
    failed = sum(1 for r in results if not r["passed"])
    context.log.info(
        "data_quality: %d checks — %d passed, %d failed", total, total - failed, failed
    )
    if failed:
        context.log.warning(
            "Failed checks: %s",
            [r for r in results if not r["passed"]],
        )
