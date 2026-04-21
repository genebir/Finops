"""CostRecommendationAsset — 규칙 기반 비용 최적화 추천 엔진."""

from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..db_schema import ensure_tables
from ..resources.duckdb_io import DuckDBResource
from ..resources.settings_store import SettingsStoreResource
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()
_REPORTS_DIR = Path(_cfg.data.reports_dir)


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["gold_marts", "gold_marts_gcp", "gold_marts_azure", "anomaly_detection"],
    description=(
        "fact_daily_cost와 anomaly_scores를 분석하여 비용 최적화 추천을 생성한다."
    ),
    group_name="analytics",
)
def cost_recommendations(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
    settings_store: SettingsStoreResource,
) -> None:
    """비용 최적화 추천 생성."""
    settings_store.ensure_table()
    partition_key = context.partition_key
    month_str = partition_key[:7]
    year_month = month_str.replace("-", "")
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with duckdb_resource.get_connection() as conn:
        ensure_tables(conn, "fact_daily_cost", "dim_cost_recommendations", "anomaly_scores")
        cur = conn.cursor()
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='fact_daily_cost'"
        )
        if not cur.fetchone():
            context.log.warning("fact_daily_cost 없음 — cost_recommendations 건너뜀")
            cur.close()
            return

        # Rule 1: idle 리소스
        cur.execute("""
            WITH month_costs AS (
                SELECT resource_id, team, product, env, provider,
                    SUM(CAST(effective_cost AS DOUBLE PRECISION)) AS total_cost,
                    MAX(charge_date) AS last_charge_date,
                    COUNT(*) AS charge_days
                FROM fact_daily_cost
                WHERE to_char(charge_date, 'YYYY-MM') = %s
                GROUP BY resource_id, team, product, env, provider
            ),
            recent_costs AS (
                SELECT resource_id,
                    SUM(CAST(effective_cost AS DOUBLE PRECISION)) AS recent_cost
                FROM fact_daily_cost
                WHERE to_char(charge_date, 'YYYY-MM') = %s
                  AND charge_date >= (%s || '-01')::DATE + INTERVAL '21 days'
                GROUP BY resource_id
            )
            SELECT m.resource_id, m.team, m.product, m.env, m.provider,
                   m.total_cost, m.last_charge_date
            FROM month_costs m
            LEFT JOIN recent_costs r ON m.resource_id = r.resource_id
            WHERE m.charge_days >= 3
              AND (r.recent_cost IS NULL OR r.recent_cost = 0)
              AND m.total_cost > 0
        """, [month_str, month_str, month_str])
        idle_rows = cur.fetchall()

        # Rule 2: high_growth
        prev_month_parts = month_str.split("-")
        prev_month_year = int(prev_month_parts[0])
        prev_month_num = int(prev_month_parts[1]) - 1
        if prev_month_num == 0:
            prev_month_year -= 1
            prev_month_num = 12
        prev_month_str = f"{prev_month_year:04d}-{prev_month_num:02d}"

        cur.execute("""
            WITH cur_costs AS (
                SELECT resource_id, team, product, env, provider,
                    SUM(CAST(effective_cost AS DOUBLE PRECISION)) AS cur_cost
                FROM fact_daily_cost
                WHERE to_char(charge_date, 'YYYY-MM') = %s
                GROUP BY resource_id, team, product, env, provider
            ),
            prev_costs AS (
                SELECT resource_id,
                    SUM(CAST(effective_cost AS DOUBLE PRECISION)) AS prev_cost
                FROM fact_daily_cost
                WHERE to_char(charge_date, 'YYYY-MM') = %s
                GROUP BY resource_id
            )
            SELECT c.resource_id, c.team, c.product, c.env, c.provider,
                   c.cur_cost, p.prev_cost,
                   (c.cur_cost - p.prev_cost) / p.prev_cost * 100 AS growth_pct
            FROM cur_costs c
            JOIN prev_costs p ON c.resource_id = p.resource_id
            WHERE p.prev_cost > 10
              AND c.cur_cost > p.prev_cost * 1.5
            ORDER BY growth_pct DESC
        """, [month_str, prev_month_str])
        growth_rows = cur.fetchall()

        # Rule 3: persistent_anomaly
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='anomaly_scores'"
        )
        anomaly_rows_raw = []
        if cur.fetchone():
            cur.execute("""
                SELECT resource_id, team, product, env,
                    COUNT(*) AS anomaly_count,
                    SUM(CASE WHEN severity='critical' THEN 1 ELSE 0 END) AS critical_count
                FROM anomaly_scores
                WHERE to_char(charge_date, 'YYYY-MM') = %s
                GROUP BY resource_id, team, product, env
                HAVING COUNT(*) >= 3
            """, [month_str])
            anomaly_rows_raw = cur.fetchall()

        cur.close()

    context.log.info(
        f"[Recommendations] idle={len(idle_rows)}, growth={len(growth_rows)}, "
        f"persistent_anomaly={len(anomaly_rows_raw)}"
    )

    recommendations: list[dict[str, object]] = []

    for row in idle_rows:
        resource_id, team, product, env, provider, total_cost, _ = row
        recommendations.append({
            "billing_month": month_str, "resource_id": resource_id,
            "team": team, "product": product, "env": env, "provider": provider,
            "recommendation_type": "idle",
            "reason": f"마지막 7일간 비용 없음 (월 총비용 ${float(total_cost):.2f})",
            "estimated_savings": float(total_cost) * 0.3, "severity": "warning",
        })

    for row in growth_rows:
        resource_id, team, product, env, provider, cur_cost, prev_cost, growth_pct = row
        severity = "critical" if float(growth_pct) >= 100 else "warning"
        recommendations.append({
            "billing_month": month_str, "resource_id": resource_id,
            "team": team, "product": product, "env": env, "provider": provider,
            "recommendation_type": "high_growth",
            "reason": f"전월 대비 {float(growth_pct):.1f}% 비용 급증",
            "estimated_savings": float(cur_cost) - float(prev_cost), "severity": severity,
        })

    for row in anomaly_rows_raw:
        resource_id, team, product, env, anomaly_count, critical_count = row
        severity = "critical" if int(critical_count) >= 2 else "warning"
        recommendations.append({
            "billing_month": month_str, "resource_id": resource_id,
            "team": team, "product": product, "env": env, "provider": "unknown",
            "recommendation_type": "persistent_anomaly",
            "reason": f"해당 월 이상치 {int(anomaly_count)}회 탐지 (critical {int(critical_count)}회)",
            "estimated_savings": None, "severity": severity,
        })

    if not recommendations:
        context.log.info(f"[Recommendations] No recommendations for {month_str}")
        return

    result_df = pl.DataFrame(recommendations)

    import psycopg2.extras

    with duckdb_resource.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM dim_cost_recommendations WHERE billing_month = %s", [month_str]
        )
        values = [
            (r["billing_month"], r["resource_id"], r["team"], r["product"], r["env"],
             r["provider"], r["recommendation_type"], r["reason"],
             r["estimated_savings"], r["severity"])
            for r in recommendations
        ]
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO dim_cost_recommendations
                (billing_month, resource_id, team, product, env, provider,
                 recommendation_type, reason, estimated_savings, severity)
            VALUES %s
            """,
            values, page_size=500,
        )
        cur.close()

    result_df.write_csv(str(_REPORTS_DIR / f"recommendations_{year_month}.csv"))
    context.log.info(
        f"[Recommendations] Saved {len(recommendations)} recommendations for {month_str}"
    )
