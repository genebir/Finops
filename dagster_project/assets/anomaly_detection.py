"""Anomaly Detection Asset — 멀티 탐지기 기반 이상치 탐지."""

from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, asset

from ..config import load_config
from ..core.anomaly_detector import AnomalyResult
from ..detectors.zscore_detector import ZScoreDetector
from ..resources.duckdb_io import DuckDBResource
from ..resources.settings_store import SettingsStoreResource
from .raw_cur import MONTHLY_PARTITIONS

_cfg = load_config()
_REPORTS_DIR = Path(_cfg.data.reports_dir)


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["gold_marts"],
    description=(
        "fact_daily_cost를 읽어 설정된 탐지기(Z-score, IsolationForest)로 이상치를 탐지하고 "
        "anomaly_scores 테이블(PostgreSQL)과 data/reports/anomalies_YYYYMM.csv를 생성한다."
    ),
    group_name="analytics",
)
def anomaly_detection(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
    settings_store: SettingsStoreResource,
) -> None:
    """멀티 탐지기 이상치 탐지 실행."""
    partition_key = context.partition_key
    month_str = partition_key[:7]
    year_month = month_str.replace("-", "")
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _REPORTS_DIR / f"anomalies_{year_month}.csv"

    with duckdb_resource.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='fact_daily_cost'"
        )
        if not cur.fetchone():
            context.log.warning("fact_daily_cost not found — skipping anomaly detection")
            cur.close()
            return

        cur.execute(
            """
            SELECT charge_date, resource_id, cost_unit_key, team, product, env,
                   CAST(effective_cost AS DOUBLE PRECISION) AS effective_cost
            FROM fact_daily_cost
            WHERE to_char(charge_date, 'YYYY-MM') = %s
            ORDER BY resource_id, charge_date
            """,
            [month_str],
        )
        columns = [desc[0] for desc in cur.description]
        rows_raw = cur.fetchall()
        cur.close()

    if not rows_raw:
        context.log.warning(f"No data for partition {partition_key} — skipping")
        return

    df = pl.DataFrame(rows_raw, schema=columns, orient="row")
    context.log.info(f"Loaded {len(df)} rows from fact_daily_cost for {month_str}")

    settings_store.ensure_table()
    active_detectors_str = settings_store.get_str("anomaly.active_detectors", "zscore")
    active_detectors = [d.strip() for d in active_detectors_str.split(",") if d.strip()]
    context.log.info(f"Active detectors: {active_detectors}")

    all_anomalies: list[AnomalyResult] = []

    if "zscore" in active_detectors:
        threshold_warning = settings_store.get_float(
            "anomaly.zscore.warning", _cfg.operational_defaults.anomaly_zscore_warning
        )
        threshold_critical = settings_store.get_float(
            "anomaly.zscore.critical", _cfg.operational_defaults.anomaly_zscore_critical
        )
        zscore_anomalies = ZScoreDetector(
            threshold_warning=threshold_warning,
            threshold_critical=threshold_critical,
        ).detect(df)
        all_anomalies.extend(zscore_anomalies)
        context.log.info(f"Z-score: {len(zscore_anomalies)}개 이상치")

    if "isolation_forest" in active_detectors:
        try:
            from ..detectors.isolation_forest_detector import IsolationForestDetector

            if_anomalies = IsolationForestDetector(
                contamination=settings_store.get_float("isolation_forest.contamination", 0.05),
                n_estimators=settings_store.get_int("isolation_forest.n_estimators", 100),
                random_state=settings_store.get_int("isolation_forest.random_state", 42),
                score_critical=settings_store.get_float("isolation_forest.score_critical", -0.20),
                score_warning=settings_store.get_float("isolation_forest.score_warning", -0.05),
            ).detect(df)
            all_anomalies.extend(if_anomalies)
            context.log.info(f"IsolationForest: {len(if_anomalies)}개 이상치")
        except ImportError:
            context.log.warning("scikit-learn 미설치 — isolation_forest 건너뜀")

    if "moving_average" in active_detectors:
        from ..detectors.moving_average_detector import MovingAverageDetector

        ma_anomalies = MovingAverageDetector(
            window_days=settings_store.get_int("moving_average.window_days", 7),
            multiplier_warning=settings_store.get_float("moving_average.multiplier_warning", 2.0),
            multiplier_critical=settings_store.get_float("moving_average.multiplier_critical", 3.0),
            min_window=settings_store.get_int("moving_average.min_window", 3),
        ).detect(df)
        all_anomalies.extend(ma_anomalies)
        context.log.info(f"MovingAverage: {len(ma_anomalies)}개 이상치")

    if "arima" in active_detectors:
        try:
            from ..detectors.arima_detector import ArimaDetector

            arima_anomalies = ArimaDetector(
                order=(
                    settings_store.get_int("arima.order_p", 1),
                    settings_store.get_int("arima.order_d", 1),
                    settings_store.get_int("arima.order_q", 1),
                ),
                threshold_warning=settings_store.get_float("arima.threshold_warning", 2.0),
                threshold_critical=settings_store.get_float("arima.threshold_critical", 3.0),
                min_samples=settings_store.get_int("arima.min_samples", 10),
            ).detect(df)
            all_anomalies.extend(arima_anomalies)
            context.log.info(f"ARIMA: {len(arima_anomalies)}개 이상치")
        except ImportError:
            context.log.warning("statsmodels 미설치 — arima 건너뜀")

    if "autoencoder" in active_detectors:
        try:
            from ..detectors.autoencoder_detector import AutoencoderDetector

            ae_anomalies = AutoencoderDetector(
                window_size=settings_store.get_int("autoencoder.window_size", 7),
                threshold_warning=settings_store.get_float("autoencoder.threshold_warning", 2.0),
                threshold_critical=settings_store.get_float("autoencoder.threshold_critical", 3.0),
                min_samples=settings_store.get_int("autoencoder.min_samples", 14),
                max_iter=settings_store.get_int("autoencoder.max_iter", 200),
            ).detect(df)
            all_anomalies.extend(ae_anomalies)
            context.log.info(f"Autoencoder: {len(ae_anomalies)}개 이상치")
        except ImportError:
            context.log.warning("scikit-learn 미설치 — autoencoder 건너뜀")

    context.log.info(
        f"Total anomalies: {len(all_anomalies)} "
        f"(critical: {sum(1 for a in all_anomalies if a.severity == 'critical')}, "
        f"warning: {sum(1 for a in all_anomalies if a.severity == 'warning')})"
    )

    anomaly_rows = [
        (
            a.resource_id, a.cost_unit_key, a.team, a.product, a.env,
            a.charge_date.isoformat(), float(a.effective_cost),
            float(a.mean_cost), float(a.std_cost), a.z_score,
            a.is_anomaly, a.severity, a.detector_name,
        )
        for a in all_anomalies
    ]

    anomaly_df = pl.DataFrame(
        [
            {
                "resource_id": a.resource_id, "cost_unit_key": a.cost_unit_key,
                "team": a.team, "product": a.product, "env": a.env,
                "charge_date": a.charge_date.isoformat(),
                "effective_cost": float(a.effective_cost),
                "mean_cost": float(a.mean_cost), "std_cost": float(a.std_cost),
                "z_score": a.z_score, "is_anomaly": a.is_anomaly,
                "severity": a.severity, "detector_name": a.detector_name,
            }
            for a in all_anomalies
        ]
    ) if all_anomalies else _empty_anomaly_df()

    with duckdb_resource.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM anomaly_scores WHERE to_char(charge_date, 'YYYY-MM') = %s",
            [month_str],
        )
        if anomaly_rows:
            import psycopg2.extras

            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO anomaly_scores
                    (resource_id, cost_unit_key, team, product, env,
                     charge_date, effective_cost, mean_cost, std_cost,
                     z_score, is_anomaly, severity, detector_name)
                VALUES %s
                """,
                anomaly_rows,
                page_size=500,
            )
            context.log.info(f"Inserted {len(anomaly_rows)} rows into anomaly_scores")
        cur.close()

    anomaly_df.write_csv(str(output_path))
    context.log.info(f"Wrote anomaly report to {output_path}")


def _empty_anomaly_df() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "resource_id": pl.Utf8, "cost_unit_key": pl.Utf8,
            "team": pl.Utf8, "product": pl.Utf8, "env": pl.Utf8,
            "charge_date": pl.Utf8, "effective_cost": pl.Float64,
            "mean_cost": pl.Float64, "std_cost": pl.Float64,
            "z_score": pl.Float64, "is_anomaly": pl.Boolean,
            "severity": pl.Utf8, "detector_name": pl.Utf8,
        }
    )
