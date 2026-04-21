"""CostRecommendationAsset — 규칙 기반 비용 최적화 추천 엔진."""

from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..resources.duckdb_io import DuckDBResource
from ..resources.settings_store import SettingsStoreResource
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()
_REPORTS_DIR = Path(_cfg.data.reports_dir)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dim_cost_recommendations (
    billing_month       VARCHAR        NOT NULL,
    resource_id         VARCHAR        NOT NULL,
    team                VARCHAR,
    product             VARCHAR,
    env                 VARCHAR,
    provider            VARCHAR,
    recommendation_type VARCHAR        NOT NULL,
    reason              VARCHAR        NOT NULL,
    estimated_savings   DECIMAL(18, 6),
    severity            VARCHAR        NOT NULL,
    PRIMARY KEY (billing_month, resource_id, recommendation_type)
)
"""


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["gold_marts", "gold_marts_gcp", "gold_marts_azure", "anomaly_detection"],
    description=(
        "fact_daily_cost와 anomaly_scores를 분석하여 비용 최적화 추천을 생성한다. "
        "idle 리소스, 급성장 리소스, 지속 이상치 리소스를 탐지하여 "
        "dim_cost_recommendations 테이블과 CSV 보고서를 출력한다."
    ),
    group_name="analytics",
)
def cost_recommendations(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
    settings_store: SettingsStoreResource,
) -> None:
    """비용 최적화 추천 생성.

    세 가지 규칙을 적용한다:
    1. idle: 해당 월에 비용이 있었지만 마지막 7일간 비용이 없는 리소스
    2. high_growth: 전월 대비 비용 증가율이 50% 이상인 리소스
    3. persistent_anomaly: 해당 월에 3회 이상 이상치가 탐지된 리소스
    """
    settings_store.ensure_table()
    partition_key = context.partition_key
    month_str = partition_key[:7]
    year_month = month_str.replace("-", "")
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with duckdb_resource.get_connection() as conn:
        has_fact = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name='fact_daily_cost'"
        ).fetchone()
        if not has_fact:
            context.log.warning("fact_daily_cost 없음 — cost_recommendations 건너뜀")
            return

        conn.execute(_CREATE_TABLE_SQL)

        # Rule 1: idle 리소스 (월 초반엔 비용 있었지만 마지막 7일간 비용 없음)
        idle_rows = conn.execute(f"""
            WITH month_costs AS (
                SELECT resource_id, team, product, env, provider,
                    SUM(CAST(effective_cost AS DOUBLE)) AS total_cost,
                    MAX(charge_date) AS last_charge_date,
                    COUNT(*) AS charge_days
                FROM fact_daily_cost
                WHERE STRFTIME(charge_date, '%Y-%m') = '{month_str}'
                GROUP BY resource_id, team, product, env, provider
            ),
            recent_costs AS (
                SELECT resource_id,
                    SUM(CAST(effective_cost AS DOUBLE)) AS recent_cost
                FROM fact_daily_cost
                WHERE STRFTIME(charge_date, '%Y-%m') = '{month_str}'
                  AND charge_date >= DATE_TRUNC('month', DATE '{month_str}-01') + INTERVAL 21 DAYS
                GROUP BY resource_id
            )
            SELECT m.resource_id, m.team, m.product, m.env, m.provider,
                   m.total_cost, m.last_charge_date
            FROM month_costs m
            LEFT JOIN recent_costs r ON m.resource_id = r.resource_id
            WHERE m.charge_days >= 3
              AND (r.recent_cost IS NULL OR r.recent_cost = 0)
              AND m.total_cost > 0
        """).fetchdf()

        # Rule 2: high_growth 리소스 (전월 대비 50% 이상 급증)
        prev_month_parts = month_str.split("-")
        prev_month_year = int(prev_month_parts[0])
        prev_month_num = int(prev_month_parts[1]) - 1
        if prev_month_num == 0:
            prev_month_year -= 1
            prev_month_num = 12
        prev_month_str = f"{prev_month_year:04d}-{prev_month_num:02d}"

        growth_rows = conn.execute(f"""
            WITH cur_costs AS (
                SELECT resource_id, team, product, env, provider,
                    SUM(CAST(effective_cost AS DOUBLE)) AS cur_cost
                FROM fact_daily_cost
                WHERE STRFTIME(charge_date, '%Y-%m') = '{month_str}'
                GROUP BY resource_id, team, product, env, provider
            ),
            prev_costs AS (
                SELECT resource_id,
                    SUM(CAST(effective_cost AS DOUBLE)) AS prev_cost
                FROM fact_daily_cost
                WHERE STRFTIME(charge_date, '%Y-%m') = '{prev_month_str}'
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
        """).fetchdf()

        # Rule 3: persistent_anomaly (해당 월 이상치 3회 이상)
        has_anomaly = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name='anomaly_scores'"
        ).fetchone()

        anomaly_rows = None
        if has_anomaly:
            anomaly_rows = conn.execute(f"""
                SELECT resource_id, team, product, env,
                    COUNT(*) AS anomaly_count,
                    SUM(CASE WHEN severity='critical' THEN 1 ELSE 0 END) AS critical_count
                FROM anomaly_scores
                WHERE STRFTIME(charge_date, '%Y-%m') = '{month_str}'
                GROUP BY resource_id, team, product, env
                HAVING COUNT(*) >= 3
            """).fetchdf()

    import pandas as pd

    idle_df = idle_rows if isinstance(idle_rows, pd.DataFrame) else pd.DataFrame()
    growth_df = growth_rows if isinstance(growth_rows, pd.DataFrame) else pd.DataFrame()
    anomaly_df = anomaly_rows if isinstance(anomaly_rows, pd.DataFrame) else pd.DataFrame()

    context.log.info(
        f"[Recommendations] idle={len(idle_df)}, growth={len(growth_df)}, "
        f"persistent_anomaly={len(anomaly_df)}"
    )

    recommendations: list[dict[str, object]] = []

    for _, row in idle_df.iterrows():
        recommendations.append({
            "billing_month": month_str,
            "resource_id": row["resource_id"],
            "team": row["team"],
            "product": row["product"],
            "env": row["env"],
            "provider": row["provider"],
            "recommendation_type": "idle",
            "reason": f"마지막 7일간 비용 없음 (월 총비용 ${float(row['total_cost']):.2f})",
            "estimated_savings": float(row["total_cost"]) * 0.3,
            "severity": "warning",
        })

    for _, row in growth_df.iterrows():
        growth_pct = float(row["growth_pct"])
        severity = "critical" if growth_pct >= 100 else "warning"
        recommendations.append({
            "billing_month": month_str,
            "resource_id": row["resource_id"],
            "team": row["team"],
            "product": row["product"],
            "env": row["env"],
            "provider": row["provider"],
            "recommendation_type": "high_growth",
            "reason": f"전월 대비 {growth_pct:.1f}% 비용 급증",
            "estimated_savings": float(row["cur_cost"]) - float(row["prev_cost"]),
            "severity": severity,
        })

    for _, row in anomaly_df.iterrows():
        count = int(row["anomaly_count"])
        critical_count = int(row["critical_count"])
        severity = "critical" if critical_count >= 2 else "warning"
        recommendations.append({
            "billing_month": month_str,
            "resource_id": row["resource_id"],
            "team": row["team"],
            "product": row["product"],
            "env": row["env"],
            "provider": "unknown",
            "recommendation_type": "persistent_anomaly",
            "reason": f"해당 월 이상치 {count}회 탐지 (critical {critical_count}회)",
            "estimated_savings": None,
            "severity": severity,
        })

    if not recommendations:
        context.log.info(f"[Recommendations] No recommendations for {month_str}")
        return

    result_df = pl.DataFrame(recommendations)

    with duckdb_resource.get_connection() as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute(
            "DELETE FROM dim_cost_recommendations WHERE billing_month = ?", [month_str]
        )
        conn.register("_recs", result_df.to_arrow())
        conn.execute("""
            INSERT INTO dim_cost_recommendations
                (billing_month, resource_id, team, product, env, provider,
                 recommendation_type, reason, estimated_savings, severity)
            SELECT billing_month, resource_id, team, product, env, provider,
                   recommendation_type, reason,
                   CAST(estimated_savings AS DECIMAL(18,6)),
                   severity
            FROM _recs
        """)

    result_df.write_csv(str(_REPORTS_DIR / f"recommendations_{year_month}.csv"))
    context.log.info(
        f"[Recommendations] Saved {len(recommendations)} recommendations for {month_str}"
    )
