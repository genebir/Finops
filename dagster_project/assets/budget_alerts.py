"""Budget Alerts Asset — 팀/환경별 예산 사용률 계산 및 초과 알림."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..core.alert_sink import Alert
from ..resources.budget_store import BudgetStoreResource
from ..resources.duckdb_io import DuckDBResource
from ..resources.settings_store import SettingsStoreResource
from ..sinks.console_sink import ConsoleSink
from ..sinks.slack_sink import SlackSink
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()

_CREATE_STATUS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dim_budget_status (
    billing_month  VARCHAR        NOT NULL,
    team           VARCHAR        NOT NULL,
    env            VARCHAR        NOT NULL,
    budget_amount  DECIMAL(18, 6) NOT NULL,
    actual_cost    DECIMAL(18, 6) NOT NULL,
    utilization_pct DOUBLE        NOT NULL,
    status         VARCHAR        NOT NULL,  -- 'ok' | 'warning' | 'over'
    updated_at     TIMESTAMPTZ    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (billing_month, team, env)
)
"""


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["gold_marts", "gold_marts_gcp", "gold_marts_azure"],
    description=(
        "fact_daily_cost를 팀/환경별로 집계하여 dim_budget과 비교하고 "
        "예산 사용률을 dim_budget_status에 저장한다. "
        "임계값 초과 시 Alert를 발송한다."
    ),
    group_name="reporting",
)
def budget_alerts(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
    budget_store: BudgetStoreResource,
    settings_store: SettingsStoreResource,
) -> None:
    """팀/환경 단위 예산 사용률 계산 및 초과 알림 발송.

    - dim_budget에서 (team, env) 예산 조회 (와일드카드 폴백 포함)
    - fact_daily_cost에서 해당 월 실제 비용 집계
    - utilization_pct = actual / budget * 100
    - warning: >= budget.alert_threshold_pct (기본 80%)
    - over: >= budget.over_threshold_pct (기본 100%)
    """
    budget_store.ensure_table()
    settings_store.ensure_table()

    warn_threshold = settings_store.get_float("budget.alert_threshold_pct", 80.0)
    over_threshold = settings_store.get_float("budget.over_threshold_pct", 100.0)

    partition_key = context.partition_key
    month_str = partition_key[:7]
    year_month = month_str.replace("-", "")
    reports_dir = Path(_cfg.data.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=UTC)

    with duckdb_resource.get_connection() as conn:
        conn.execute(_CREATE_STATUS_TABLE_SQL)

        has_fact = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name='fact_daily_cost'"
        ).fetchone()
        if not has_fact:
            context.log.warning("fact_daily_cost 테이블 없음 — budget_alerts 건너뜀")
            return

        arrow = conn.execute(f"""
            SELECT
                team,
                env,
                SUM(CAST(effective_cost AS DOUBLE)) AS actual_cost
            FROM fact_daily_cost
            WHERE STRFTIME(charge_date, '%Y-%m') = '{month_str}'
            GROUP BY team, env
        """).arrow()

    actual_df: pl.DataFrame = pl.from_arrow(arrow)  # type: ignore[arg-type]
    context.log.info(f"[Budget] {len(actual_df)} (team, env) groups for {month_str}")

    rows: list[dict[str, object]] = []
    alerts: list[Alert] = []

    for row in actual_df.iter_rows(named=True):
        team = str(row["team"])
        env = str(row["env"])
        actual = float(row["actual_cost"])
        budget = budget_store.get_budget(team, env)

        if budget is None or budget <= 0:
            continue

        utilization_pct = actual / budget * 100.0
        if utilization_pct >= over_threshold:
            status = "over"
            severity = "critical"
        elif utilization_pct >= warn_threshold:
            status = "warning"
            severity = "warning"
        else:
            status = "ok"
            severity = "info"

        rows.append({
            "billing_month": month_str,
            "team": team,
            "env": env,
            "budget_amount": budget,
            "actual_cost": actual,
            "utilization_pct": utilization_pct,
            "status": status,
        })

        if status in ("warning", "over"):
            alerts.append(
                Alert(
                    alert_type=f"budget_{status}",
                    severity=severity,
                    resource_id=f"team:{team}",
                    cost_unit_key=f"{team}:*:{env}",
                    message=(
                        f"Budget {status.upper()} [{team}/{env}] {month_str}: "
                        f"actual=${actual:.2f} vs budget=${budget:.2f} "
                        f"({utilization_pct:.1f}%)"
                    ),
                    actual_cost=Decimal(str(round(actual, 6))),
                    reference_cost=Decimal(str(round(budget, 6))),
                    deviation_pct=utilization_pct,
                    triggered_at=now,
                    extra={"team": team, "env": env, "billing_month": month_str},
                )
            )

    if rows:
        with duckdb_resource.get_connection() as conn:
            conn.execute(_CREATE_STATUS_TABLE_SQL)
            conn.execute(
                "DELETE FROM dim_budget_status WHERE billing_month = ?",
                [month_str],
            )
            status_df = pl.DataFrame(rows).with_columns([
                pl.col("budget_amount").cast(pl.Float64),
                pl.col("actual_cost").cast(pl.Float64),
            ])
            conn.register("_budget_status_rows", status_df.to_arrow())
            conn.execute("""
                INSERT INTO dim_budget_status
                    (billing_month, team, env, budget_amount, actual_cost, utilization_pct, status)
                SELECT billing_month, team, env,
                       CAST(budget_amount AS DECIMAL(18,6)),
                       CAST(actual_cost   AS DECIMAL(18,6)),
                       utilization_pct, status
                FROM _budget_status_rows
            """)
        context.log.info(f"[Budget] Saved {len(rows)} budget status rows for {month_str}")

    if alerts:
        sinks: list[ConsoleSink | SlackSink] = [ConsoleSink()]
        if SlackSink.is_configured():
            sinks.append(SlackSink())
        for sink in sinks:
            sink.send_batch(alerts)

        alert_rows = [
            {
                "billing_month": a.extra.get("billing_month", month_str),
                "team": a.extra.get("team", ""),
                "env": a.extra.get("env", ""),
                "alert_type": a.alert_type,
                "severity": a.severity,
                "actual_cost": float(a.actual_cost),
                "budget_amount": float(a.reference_cost),
                "utilization_pct": a.deviation_pct,
                "message": a.message,
                "triggered_at": a.triggered_at.isoformat(),
            }
            for a in alerts
        ]
        pl.DataFrame(alert_rows).write_csv(str(reports_dir / f"budget_alerts_{year_month}.csv"))
        context.log.info(f"[Budget] Dispatched {len(alerts)} budget alerts")
    else:
        context.log.info(f"[Budget] No budget alerts for {month_str}")
