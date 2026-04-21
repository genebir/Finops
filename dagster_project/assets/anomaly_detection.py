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

_SQL_DIR = Path(__file__).parent.parent.parent / "sql" / "marts"
_cfg = load_config()
_REPORTS_DIR = Path(_cfg.data.reports_dir)


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    deps=["gold_marts"],
    description=(
        "fact_daily_cost를 읽어 설정된 탐지기(Z-score, IsolationForest)로 이상치를 탐지하고 "
        "anomaly_scores 테이블(DuckDB)과 data/reports/anomalies_YYYYMM.csv를 생성한다."
    ),
    group_name="analytics",
)
def anomaly_detection(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
    settings_store: SettingsStoreResource,
) -> None:
    """멀티 탐지기 이상치 탐지 실행.

    platform_settings의 anomaly.active_detectors 값으로 활성 탐지기를 제어한다.
    탐지 결과는 detector_name 컬럼으로 구분되어 anomaly_scores에 저장된다.
    """
    partition_key = context.partition_key
    year_month = partition_key[:7].replace("-", "")
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _REPORTS_DIR / f"anomalies_{year_month}.csv"

    with duckdb_resource.get_connection() as conn:
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'fact_daily_cost'"
        ).fetchall()
        if not tables:
            context.log.warning("fact_daily_cost not found — skipping anomaly detection")
            return

        month_str = partition_key[:7]
        arrow = conn.execute(f"""
            SELECT
                charge_date,
                resource_id,
                cost_unit_key,
                team,
                product,
                env,
                CAST(effective_cost AS DOUBLE) AS effective_cost
            FROM fact_daily_cost
            WHERE STRFTIME(charge_date, '%Y-%m') = '{month_str}'
            ORDER BY resource_id, charge_date
        """).arrow()

    result = pl.from_arrow(arrow)
    assert isinstance(result, pl.DataFrame)
    df: pl.DataFrame = result
    context.log.info(f"Loaded {len(df)} rows from fact_daily_cost for {month_str}")

    if df.is_empty():
        context.log.warning(f"No data for partition {partition_key} — skipping")
        return

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
                contamination=settings_store.get_float(
                    "isolation_forest.contamination", 0.05
                ),
                n_estimators=settings_store.get_int(
                    "isolation_forest.n_estimators", 100
                ),
                random_state=settings_store.get_int(
                    "isolation_forest.random_state", 42
                ),
                score_critical=settings_store.get_float(
                    "isolation_forest.score_critical", -0.20
                ),
                score_warning=settings_store.get_float(
                    "isolation_forest.score_warning", -0.05
                ),
            ).detect(df)
            all_anomalies.extend(if_anomalies)
            context.log.info(f"IsolationForest: {len(if_anomalies)}개 이상치")
        except ImportError:
            context.log.warning("scikit-learn 미설치 — isolation_forest 건너뜀")

    context.log.info(
        f"Total anomalies: {len(all_anomalies)} "
        f"(critical: {sum(1 for a in all_anomalies if a.severity == 'critical')}, "
        f"warning: {sum(1 for a in all_anomalies if a.severity == 'warning')})"
    )

    rows = [
        {
            "resource_id": a.resource_id,
            "cost_unit_key": a.cost_unit_key,
            "team": a.team,
            "product": a.product,
            "env": a.env,
            "charge_date": a.charge_date.isoformat(),
            "effective_cost": float(a.effective_cost),
            "mean_cost": float(a.mean_cost),
            "std_cost": float(a.std_cost),
            "z_score": a.z_score,
            "is_anomaly": a.is_anomaly,
            "severity": a.severity,
            "detector_name": a.detector_name,
        }
        for a in all_anomalies
    ]

    anomaly_df = pl.DataFrame(rows) if rows else _empty_anomaly_df()

    with duckdb_resource.get_connection() as conn:
        create_sql = (_SQL_DIR / "anomaly_scores.sql").read_text()
        conn.execute(create_sql)
        # Phase 3 마이그레이션: detector_name 컬럼 추가
        conn.execute(
            "ALTER TABLE anomaly_scores ADD COLUMN IF NOT EXISTS detector_name VARCHAR DEFAULT 'zscore'"
        )

        conn.execute(
            "DELETE FROM anomaly_scores WHERE STRFTIME(charge_date, '%Y-%m') = ?",
            [month_str],
        )
        if rows:
            conn.register("anomaly_rows", anomaly_df.to_arrow())
            conn.execute("""
                INSERT INTO anomaly_scores
                SELECT
                    resource_id,
                    cost_unit_key,
                    team,
                    product,
                    env,
                    CAST(charge_date AS DATE),
                    CAST(effective_cost AS DECIMAL(18,6)),
                    CAST(mean_cost     AS DECIMAL(18,6)),
                    CAST(std_cost      AS DECIMAL(18,6)),
                    z_score,
                    is_anomaly,
                    severity,
                    detector_name
                FROM anomaly_rows
            """)
            context.log.info(f"Inserted {len(rows)} rows into anomaly_scores")

    anomaly_df.write_csv(str(output_path))
    context.log.info(f"Wrote anomaly report to {output_path}")


def _empty_anomaly_df() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "resource_id": pl.Utf8,
            "cost_unit_key": pl.Utf8,
            "team": pl.Utf8,
            "product": pl.Utf8,
            "env": pl.Utf8,
            "charge_date": pl.Utf8,
            "effective_cost": pl.Float64,
            "mean_cost": pl.Float64,
            "std_cost": pl.Float64,
            "z_score": pl.Float64,
            "is_anomaly": pl.Boolean,
            "severity": pl.Utf8,
            "detector_name": pl.Utf8,
        }
    )
