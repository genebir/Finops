"""Phase 2 asset을 특정 파티션에 대해 직접 실행하는 스크립트.

사용법:
    uv run python scripts/run_phase2.py [partition_key]

예시:
    uv run python scripts/run_phase2.py 2026-03-01
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dagster_project.config import load_config
from dagster_project.resources.duckdb_io import DuckDBResource
from dagster_project.resources.settings_store import SettingsStoreResource

PARTITION_KEY = sys.argv[1] if len(sys.argv) > 1 else "2026-03-01"
cfg = load_config()

duckdb_resource = DuckDBResource()
settings_store = SettingsStoreResource()


# ── Step 1: settings_store 초기화 ──────────────────────────────────────────
print("\n[1/3] settings_store 초기화...")
settings_store.ensure_table()
all_settings = settings_store.all_settings()
print(f"  platform_settings: {len(all_settings)}개 항목")
for s in all_settings:
    print(f"    {s['key']:45s} = {s['value']:8s}  ({s['description']})")


# ── Step 2: anomaly_detection ──────────────────────────────────────────────
print(f"\n[2/3] anomaly_detection 실행 (partition={PARTITION_KEY})...")
from dagster_project.detectors.zscore_detector import ZScoreDetector
import polars as pl

month_str = PARTITION_KEY[:7]
threshold_warning = settings_store.get_float("anomaly.zscore.warning", 2.0)
threshold_critical = settings_store.get_float("anomaly.zscore.critical", 3.0)

with duckdb_resource.get_connection() as conn:
    cur = conn.cursor()
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
    rows = cur.fetchall()
    cur.close()

df = pl.DataFrame(rows, schema=columns, orient="row")
print(f"  데이터: {len(df)}행, 리소스: {df['resource_id'].n_unique()}개")

detector = ZScoreDetector(threshold_warning=threshold_warning, threshold_critical=threshold_critical)
anomalies = detector.detect(df)
critical = [a for a in anomalies if a.severity == "critical"]
warning = [a for a in anomalies if a.severity == "warning"]
print(f"  이상치 탐지: critical={len(critical)}, warning={len(warning)}")

for a in critical[:5]:
    print(f"    [CRITICAL] {a.resource_id} | date={a.charge_date} | "
          f"cost={float(a.effective_cost):.2f} | mean={float(a.mean_cost):.2f} | z={a.z_score:.2f}")
for a in warning[:3]:
    print(f"    [WARNING]  {a.resource_id} | date={a.charge_date} | "
          f"cost={float(a.effective_cost):.2f} | z={a.z_score:.2f}")

output_csv = Path(cfg.data.reports_dir) / f"anomalies_{PARTITION_KEY[:7].replace('-', '')}.csv"
Path(cfg.data.reports_dir).mkdir(parents=True, exist_ok=True)
if anomalies:
    import polars as pl
    anomaly_rows = [
        {
            "resource_id": a.resource_id,
            "cost_unit_key": a.cost_unit_key,
            "team": a.team,
            "charge_date": a.charge_date.isoformat(),
            "effective_cost": float(a.effective_cost),
            "mean_cost": float(a.mean_cost),
            "z_score": a.z_score,
            "severity": a.severity,
        }
        for a in anomalies
    ]
    pl.DataFrame(anomaly_rows).write_csv(str(output_csv))
print(f"  → {output_csv} 저장 ({len(anomalies)}행)")


# ── Step 3: prophet_forecast ───────────────────────────────────────────────
print("\n[3/3] prophet_forecast 실행...")
from dagster_project.providers.prophet_provider import ProphetProvider

with duckdb_resource.get_connection() as conn:
    cur = conn.cursor()
    cur.execute("""
        SELECT charge_date, resource_id, CAST(effective_cost AS DOUBLE PRECISION) AS effective_cost
        FROM fact_daily_cost ORDER BY resource_id, charge_date
    """)
    columns_all = [desc[0] for desc in cur.description]
    rows_all = cur.fetchall()
    cur.close()

df_all = pl.DataFrame(rows_all, schema=columns_all, orient="row")

try:
    provider = ProphetProvider(
        forecast_horizon_days=cfg.prophet.forecast_horizon_days,
        seasonality_mode=cfg.prophet.seasonality_mode,
    )
    records = provider.forecast_from_df(df_all)
    print(f"  Prophet 예측 완료: {len(records)}개 리소스")
    for r in sorted(records, key=lambda x: float(x.monthly_cost), reverse=True)[:5]:
        print(f"    {r.resource_address:40s} → ${float(r.monthly_cost):.2f}/월")

    prophet_csv = Path(cfg.data.reports_dir) / f"prophet_forecast_{PARTITION_KEY[:7].replace('-','')}.csv"
    pl.DataFrame([
        {"resource_id": r.resource_address, "predicted_monthly_cost": float(r.monthly_cost)}
        for r in records
    ]).write_csv(str(prophet_csv))
    print(f"  → {prophet_csv} 저장")
except ImportError:
    print("  prophet 미설치 — 건너뜀 (uv add prophet으로 설치)")


print("\n완료! data/reports/ 폴더를 확인하세요.")
