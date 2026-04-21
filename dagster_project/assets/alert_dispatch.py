"""Alert Dispatch Asset — 이상치·편차 결과를 AlertSink로 발송."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..core.alert_sink import Alert
from ..resources.duckdb_io import DuckDBResource
from ..resources.settings_store import SettingsStoreResource
from ..sinks.console_sink import ConsoleSink
from ..sinks.slack_sink import SlackSink
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()
_REPORTS_DIR = Path(_cfg.data.reports_dir)


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["anomaly_detection", "variance"],
    description=(
        "anomaly_scores(severity=critical/warning)와 variance(status=over/under)를 읽어 "
        "Alert를 생성하고 AlertSink로 발송한다."
    ),
    group_name="reporting",
)
def alert_dispatch(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
    settings_store: SettingsStoreResource,
) -> None:
    """이상치 및 편차 결과를 AlertSink로 발송한다."""
    settings_store.ensure_table()
    alert_critical_pct = settings_store.get_float(
        "alert.critical_deviation_pct", _cfg.operational_defaults.alert_critical_pct
    )

    partition_key = context.partition_key
    month_str = partition_key[:7]
    year_month = month_str.replace("-", "")
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _REPORTS_DIR / f"alerts_{year_month}.csv"

    alerts: list[Alert] = []
    now = datetime.now(tz=UTC)

    with duckdb_resource.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='anomaly_scores'"
        )
        if cur.fetchone():
            cur.execute("""
                SELECT resource_id, cost_unit_key,
                       CAST(effective_cost AS DOUBLE PRECISION),
                       CAST(mean_cost AS DOUBLE PRECISION),
                       z_score, severity
                FROM anomaly_scores
                WHERE severity IN ('critical', 'warning')
                  AND to_char(charge_date, 'YYYY-MM') = %s
            """, [month_str])
            anomaly_data = cur.fetchall()
            context.log.info(f"Anomaly alerts to dispatch: {len(anomaly_data)}")
            for resource_id, cost_unit_key, effective_cost, mean_cost, z_score, severity in anomaly_data:
                actual = Decimal(str(effective_cost))
                mean = Decimal(str(mean_cost))
                dev_pct = float(z_score) * 100.0
                alerts.append(
                    Alert(
                        alert_type="anomaly", severity=severity,
                        resource_id=resource_id, cost_unit_key=cost_unit_key,
                        message=(
                            f"Cost anomaly detected on {resource_id}: "
                            f"actual=${float(actual):.2f} (mean=${float(mean):.2f}, "
                            f"z={float(z_score):.2f})"
                        ),
                        actual_cost=actual, reference_cost=mean,
                        deviation_pct=dev_pct, triggered_at=now,
                    )
                )
        cur.close()

    variance_path = _REPORTS_DIR / f"variance_{year_month}.csv"
    if variance_path.exists():
        variance_df = pl.read_csv(str(variance_path))
        triggered = variance_df.filter(pl.col("status").is_in(["over", "under"]))
        context.log.info(f"Variance alerts to dispatch: {len(triggered)}")
        for row in triggered.iter_rows(named=True):
            actual = Decimal(str(row["actual_mtd"]))
            forecast = Decimal(str(row["forecast_monthly"]))
            dev_pct = float(row["variance_pct"]) if row["variance_pct"] is not None else 0.0
            alert_type = "variance_over" if row["status"] == "over" else "variance_under"
            severity = "critical" if abs(dev_pct) >= alert_critical_pct else "warning"
            alerts.append(
                Alert(
                    alert_type=alert_type, severity=severity,
                    resource_id=str(row["resource_id"]),
                    cost_unit_key=str(row.get("cost_unit_key", "unknown")),
                    message=(
                        f"Budget {row['status'].upper()} on {row['resource_id']}: "
                        f"actual=${float(actual):.2f} vs forecast=${float(forecast):.2f} "
                        f"({dev_pct:+.1f}%)"
                    ),
                    actual_cost=actual, reference_cost=forecast,
                    deviation_pct=dev_pct, triggered_at=now,
                )
            )

    sinks: list[ConsoleSink | SlackSink] = [ConsoleSink()]
    if SlackSink.is_configured():
        sinks.append(SlackSink())
        context.log.info("SlackSink enabled")

    for sink in sinks:
        sink.send_batch(alerts)

    context.log.info(
        f"Dispatched {len(alerts)} alerts "
        f"(anomaly: {sum(1 for a in alerts if a.alert_type == 'anomaly')}, "
        f"variance: {sum(1 for a in alerts if 'variance' in a.alert_type)})"
    )

    if alerts:
        alert_rows = [
            {
                "alert_type": a.alert_type, "severity": a.severity,
                "resource_id": a.resource_id, "cost_unit_key": a.cost_unit_key,
                "message": a.message, "actual_cost": float(a.actual_cost),
                "reference_cost": float(a.reference_cost),
                "deviation_pct": a.deviation_pct,
                "triggered_at": a.triggered_at.isoformat(),
            }
            for a in alerts
        ]
        pl.DataFrame(alert_rows).write_csv(str(output_path))
    else:
        pl.DataFrame(
            schema={
                "alert_type": pl.Utf8, "severity": pl.Utf8,
                "resource_id": pl.Utf8, "cost_unit_key": pl.Utf8,
                "message": pl.Utf8, "actual_cost": pl.Float64,
                "reference_cost": pl.Float64, "deviation_pct": pl.Float64,
                "triggered_at": pl.Utf8,
            }
        ).write_csv(str(output_path))

    context.log.info(f"Wrote alert report to {output_path}")
