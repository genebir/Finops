#!/usr/bin/env python3
"""FinOps Platform 개발환경 셋업 스크립트.

이미 완료된 단계는 자동으로 스킵한다. 언제든 다시 실행해서 부족한 부분만 채울 수 있다.

Usage:
    uv run python scripts/setup.py              # 전체 셋업
    uv run python scripts/setup.py --status      # 현재 상태만 확인
    uv run python scripts/setup.py --tables      # 테이블만 생성
    uv run python scripts/setup.py --seed        # 설정 시드만
    uv run python scripts/setup.py --materialize # Dagster asset 실행 (데이터 적재)
    uv run python scripts/setup.py --all         # 테이블 + 시드 + 데이터 적재 전부
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── 색상 ────────────────────────────────────────────────────────────────────────
USE_COLOR = sys.stdout.isatty()
GREEN = "\033[0;32m" if USE_COLOR else ""
YELLOW = "\033[1;33m" if USE_COLOR else ""
CYAN = "\033[0;36m" if USE_COLOR else ""
RED = "\033[0;31m" if USE_COLOR else ""
DIM = "\033[2m" if USE_COLOR else ""
BOLD = "\033[1m" if USE_COLOR else ""
NC = "\033[0m" if USE_COLOR else ""


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{NC} {msg}")


def skip(msg: str) -> None:
    print(f"  {DIM}– {msg} (이미 완료){NC}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{NC} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}!{NC} {msg}")


def header(msg: str) -> None:
    print(f"\n{CYAN}{BOLD}{'─' * 60}{NC}")
    print(f"{CYAN}{BOLD}  {msg}{NC}")
    print(f"{CYAN}{BOLD}{'─' * 60}{NC}")


# ── 프로젝트 루트 ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

# ── PostgreSQL 연결 ─────────────────────────────────────────────────────────────
def get_pg_conn():
    """psycopg2 connection을 반환한다. 실패 시 None."""
    try:
        import psycopg2
        from dagster_project.config import load_config
        cfg = load_config()
        conn = psycopg2.connect(cfg.postgres.dsn)
        conn.autocommit = True
        return conn
    except Exception as e:
        fail(f"PostgreSQL 연결 실패: {e}")
        return None


def table_exists(conn, name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename=%s",
            (name,),
        )
        return cur.fetchone() is not None


def table_row_count(conn, name: str) -> int:
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {name}")  # noqa: S608
            row = cur.fetchone()
            return row[0] if row else 0
    except Exception:
        return -1


# ─────────────────────────────────────────────────────────────────────────────────
# 1. 사전 조건 확인
# ─────────────────────────────────────────────────────────────────────────────────
def check_prerequisites() -> dict[str, bool]:
    header("1. 사전 조건 확인")
    results: dict[str, bool] = {}

    # .env
    env_ok = (ROOT / ".env").exists()
    if env_ok:
        skip(".env 파일")
    else:
        if (ROOT / ".env.example").exists():
            shutil.copy(ROOT / ".env.example", ROOT / ".env")
            ok(".env 파일 생성 (.env.example 복사)")
            env_ok = True
        else:
            fail(".env.example 없음 — .env를 수동 생성하세요")
    results["env"] = env_ok

    # data dirs
    dirs = ["data/warehouse", "data/reports", ".dagster"]
    all_dirs_ok = True
    for d in dirs:
        p = ROOT / d
        if p.exists():
            continue
        p.mkdir(parents=True, exist_ok=True)
        all_dirs_ok = False
    if all_dirs_ok:
        skip("데이터 디렉토리 (data/warehouse, data/reports, .dagster)")
    else:
        ok("데이터 디렉토리 생성")
    results["dirs"] = True

    # Python deps
    venv_ok = (ROOT / ".venv").exists()
    if venv_ok:
        skip("Python 의존성 (.venv)")
    else:
        warn("Python 의존성 미설치 — `uv sync` 를 실행하세요")
    results["venv"] = venv_ok

    # Node modules
    node_ok = (ROOT / "web-app" / "node_modules").exists()
    if node_ok:
        skip("Node.js 의존성 (web-app/node_modules)")
    else:
        warn("Node.js 의존성 미설치 — `cd web-app && npm install` 을 실행하세요")
    results["node"] = node_ok

    # PostgreSQL
    conn = get_pg_conn()
    if conn:
        skip("PostgreSQL 연결")
        conn.close()
        results["pg"] = True
    else:
        results["pg"] = False

    return results


# ─────────────────────────────────────────────────────────────────────────────────
# 2. 테이블 생성
# ─────────────────────────────────────────────────────────────────────────────────
def ensure_all_tables() -> tuple[int, int]:
    """모든 테이블을 CREATE IF NOT EXISTS. (created, skipped) 반환."""
    header("2. 데이터베이스 테이블 생성")

    conn = get_pg_conn()
    if not conn:
        return 0, 0

    from dagster_project.db_schema import BASE_TABLE_DDL, ensure_base_tables

    # 먼저 어떤 테이블이 이미 있는지 확인
    existing = set()
    for name in BASE_TABLE_DDL:
        if table_exists(conn, name):
            existing.add(name)

    missing_before = set(BASE_TABLE_DDL.keys()) - existing

    # ensure
    ensure_base_tables(conn)

    # platform_settings
    if not table_exists(conn, "platform_settings"):
        from dagster_project.resources.settings_store import SettingsStoreResource
        SettingsStoreResource().ensure_table()
        ok("platform_settings 테이블 생성 + 기본값 시드")
    else:
        existing.add("platform_settings")

    # dim_budget seed
    if not table_exists(conn, "dim_budget"):
        from dagster_project.resources.budget_store import BudgetStoreResource
        BudgetStoreResource().ensure_table()
        ok("dim_budget 테이블 생성 + 기본값 시드")
    else:
        existing.add("dim_budget")

    created = 0
    skipped = 0
    for name in sorted(BASE_TABLE_DDL.keys()):
        if name in existing:
            skipped += 1
        else:
            created += 1

    if created > 0:
        ok(f"{created}개 테이블 신규 생성")
    if skipped > 0:
        skip(f"{skipped}개 테이블 이미 존재")

    conn.close()
    return created, skipped


# ─────────────────────────────────────────────────────────────────────────────────
# 3. 설정 시드
# ─────────────────────────────────────────────────────────────────────────────────
def seed_settings() -> None:
    header("3. platform_settings 시드")

    conn = get_pg_conn()
    if not conn:
        return

    from dagster_project.resources.settings_store import SettingsStoreResource

    try:
        store = SettingsStoreResource()
        store.ensure_table()

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM platform_settings")
            count = cur.fetchone()[0]

        ok(f"platform_settings: {count}개 설정 항목 확인")
    except Exception as e:
        fail(f"설정 시드 실패: {e}")
    finally:
        conn.close()


def seed_budget() -> None:
    header("4. dim_budget 기본 예산 시드")

    conn = get_pg_conn()
    if not conn:
        return

    from dagster_project.resources.budget_store import BudgetStoreResource

    try:
        store = BudgetStoreResource()
        store.ensure_table()

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM dim_budget")
            count = cur.fetchone()[0]

        if count > 0:
            skip(f"dim_budget: {count}개 예산 항목 존재")
        else:
            ok("dim_budget 기본값 시드 완료")
    except Exception as e:
        fail(f"예산 시드 실패: {e}")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────────
# 5. Dagster asset 실행 (데이터 적재)
# ─────────────────────────────────────────────────────────────────────────────────

# 실행 순서가 중요한 asset 그룹 (의존성 순서)
ASSET_GROUPS: list[tuple[str, list[str]]] = [
    ("Bronze (가상 CUR 생성 → Iceberg)", [
        "raw_cur", "raw_cur_gcp", "raw_cur_azure",
        "bronze_iceberg", "bronze_iceberg_gcp", "bronze_iceberg_azure",
    ]),
    ("Silver (FOCUS 정제)", [
        "silver_focus", "silver_focus_gcp", "silver_focus_azure",
    ]),
    ("Gold (마트 적재)", [
        "gold_marts", "gold_marts_gcp", "gold_marts_azure",
    ]),
    ("분석 (이상치 탐지, 예측, 환율)", [
        "anomaly_detection", "prophet_forecast", "infracost_forecast",
        "fx_rates",
    ]),
    ("예산 / Chargeback", [
        "budget_alerts", "chargeback",
    ]),
    ("파생 마트", [
        "forecast_variance_prophet", "cost_recommendations",
        "cost_trend", "resource_inventory", "tag_policy",
        "cost_allocation", "showback_report",
        "burn_rate", "data_quality", "budget_forecast",
        "savings_tracker", "tag_compliance_score",
    ]),
    ("알림", [
        "alert_dispatch",
    ]),
]


def _has_data(conn, table: str, min_rows: int = 1) -> bool:
    """테이블이 존재하고 min_rows 이상의 데이터가 있으면 True."""
    if not table_exists(conn, table):
        return False
    return table_row_count(conn, table) >= min_rows


# asset → 결과를 확인할 주요 테이블 매핑
ASSET_TABLE_MAP: dict[str, str] = {
    "gold_marts": "fact_daily_cost",
    "gold_marts_gcp": "fact_daily_cost",
    "gold_marts_azure": "fact_daily_cost",
    "anomaly_detection": "anomaly_scores",
    "prophet_forecast": "dim_prophet_forecast",
    "infracost_forecast": "dim_forecast",
    "fx_rates": "dim_fx_rates",
    "budget_alerts": "dim_budget_status",
    "chargeback": "dim_chargeback",
    "forecast_variance_prophet": "dim_forecast_variance_prophet",
    "cost_recommendations": "dim_cost_recommendations",
    "cost_trend": "dim_cost_trend",
    "resource_inventory": "dim_resource_inventory",
    "tag_policy": "dim_tag_violations",
    "cost_allocation": "dim_allocated_cost",
    "showback_report": "dim_showback_report",
    "burn_rate": "dim_burn_rate",
    "data_quality": "dim_data_quality",
    "budget_forecast": "dim_budget_forecast",
    "savings_tracker": "dim_savings_realized",
    "tag_compliance_score": "dim_tag_compliance",
    "alert_dispatch": "dim_alert_history",
}


def materialize_assets(force: bool = False) -> None:
    header("5. Dagster asset 실행 (데이터 적재)")

    conn = get_pg_conn()
    if not conn:
        return

    # 어떤 asset이 이미 데이터가 있는지 확인
    already_done: set[str] = set()
    if not force:
        for asset, tbl in ASSET_TABLE_MAP.items():
            if _has_data(conn, tbl):
                already_done.add(asset)

    # Iceberg 관련은 Bronze/Silver 파일 존재 여부로 확인
    warehouse = ROOT / "data" / "warehouse"
    if warehouse.exists() and any(warehouse.rglob("*.parquet")):
        for a in ["raw_cur", "raw_cur_gcp", "raw_cur_azure",
                   "bronze_iceberg", "bronze_iceberg_gcp", "bronze_iceberg_azure",
                   "silver_focus", "silver_focus_gcp", "silver_focus_azure"]:
            already_done.add(a)

    assets_to_run: list[str] = []
    for group_name, assets in ASSET_GROUPS:
        group_pending = [a for a in assets if a not in already_done]
        if not group_pending:
            skip(f"{group_name}: 전체 완료")
        else:
            for a in group_pending:
                assets_to_run.append(a)
            pending_str = ", ".join(group_pending)
            warn(f"{group_name}: 실행 필요 → {pending_str}")

    conn.close()

    if not assets_to_run:
        ok("모든 asset 데이터가 이미 존재합니다.")
        return

    print(f"\n  {BOLD}총 {len(assets_to_run)}개 asset 실행 예정{NC}")
    print(f"  {DIM}(dagster.materialize 사용 — Dagster 서버 불필요){NC}\n")

    # Python 코드로 직접 materialize
    _run_materialize(assets_to_run)


def _run_materialize(asset_names: list[str]) -> None:
    """dagster.materialize()로 asset들을 순서대로 실행한다."""
    import logging
    logging.getLogger("dagster").setLevel(logging.WARNING)

    try:
        from dagster import materialize, AssetsDefinition
        from dagster_project.definitions import defs
    except ImportError as e:
        fail(f"Dagster import 실패: {e}")
        warn("  `uv sync` 로 의존성을 설치하세요.")
        return

    all_assets = list(defs.assets) if defs.assets else []
    resources = defs.resources or {}

    # asset name → AssetDefinition 매핑
    name_to_asset: dict[str, AssetsDefinition] = {}
    for asset_def in all_assets:
        if not isinstance(asset_def, AssetsDefinition):
            continue
        for key in asset_def.keys:
            name_to_asset[key.path[-1]] = asset_def

    # 그룹별 순서대로 실행
    total = len(asset_names)
    success = 0
    failed_assets: list[str] = []

    for i, name in enumerate(asset_names, 1):
        asset_def = name_to_asset.get(name)
        if asset_def is None:
            fail(f"[{i}/{total}] {name}: asset 정의를 찾을 수 없음")
            failed_assets.append(name)
            continue

        print(f"  {CYAN}[{i}/{total}]{NC} {name} 실행 중...", end="", flush=True)
        t0 = time.time()

        try:
            result = materialize(
                [asset_def],
                resources=resources,
                raise_on_error=False,
            )
            elapsed = time.time() - t0

            if result.success:
                print(f" {GREEN}✓{NC} ({elapsed:.1f}s)")
                success += 1
            else:
                print(f" {RED}✗{NC} ({elapsed:.1f}s)")
                # 에러 메시지 추출
                for event in result.all_events:
                    if event.is_step_failure:
                        err = event.step_failure_data
                        if err and err.error:
                            msg = str(err.error.message)[:200]
                            print(f"    {DIM}{msg}{NC}")
                failed_assets.append(name)
        except Exception as e:
            elapsed = time.time() - t0
            print(f" {RED}✗{NC} ({elapsed:.1f}s)")
            print(f"    {DIM}{str(e)[:200]}{NC}")
            failed_assets.append(name)

    print()
    if success == total:
        ok(f"전체 {total}개 asset 실행 완료")
    else:
        ok(f"{success}/{total}개 asset 성공")
        if failed_assets:
            fail(f"실패: {', '.join(failed_assets)}")
            warn("실패한 asset은 의존성 데이터가 없거나 선행 asset이 필요할 수 있습니다.")
            warn("다시 실행하면 성공한 부분은 스킵하고 실패한 부분만 재시도합니다.")


# ─────────────────────────────────────────────────────────────────────────────────
# 상태 보고
# ─────────────────────────────────────────────────────────────────────────────────
def show_status() -> None:
    header("현재 상태")

    conn = get_pg_conn()
    if not conn:
        return

    from dagster_project.db_schema import BASE_TABLE_DDL

    all_tables = list(BASE_TABLE_DDL.keys()) + ["platform_settings"]

    max_name = max(len(n) for n in all_tables)

    existing_count = 0
    empty_count = 0
    populated_count = 0

    print(f"\n  {'테이블':<{max_name + 2}} {'상태':>10} {'행 수':>10}")
    print(f"  {'─' * (max_name + 2)} {'─' * 10} {'─' * 10}")

    for name in sorted(all_tables):
        if not table_exists(conn, name):
            print(f"  {name:<{max_name + 2}} {RED}{'미생성':>10}{NC} {'—':>10}")
        else:
            existing_count += 1
            rows = table_row_count(conn, name)
            if rows > 0:
                populated_count += 1
                print(f"  {name:<{max_name + 2}} {GREEN}{'OK':>10}{NC} {rows:>10,}")
            else:
                empty_count += 1
                print(f"  {name:<{max_name + 2}} {YELLOW}{'비어있음':>10}{NC} {'0':>10}")

    total = len(all_tables)
    missing = total - existing_count

    print(f"\n  {BOLD}요약:{NC}")
    print(f"    전체 {total}개 | {GREEN}데이터 있음 {populated_count}{NC} | {YELLOW}비어있음 {empty_count}{NC} | {RED}미생성 {missing}{NC}")

    # Iceberg warehouse
    wh = ROOT / "data" / "warehouse"
    parquet_count = len(list(wh.rglob("*.parquet"))) if wh.exists() else 0
    if parquet_count > 0:
        print(f"    Iceberg warehouse: {GREEN}{parquet_count}개 parquet 파일{NC}")
    else:
        print(f"    Iceberg warehouse: {YELLOW}비어있음{NC}")

    conn.close()

    # 다음 단계 안내
    if missing > 0:
        print(f"\n  {BOLD}다음 단계:{NC}")
        print(f"    uv run python scripts/setup.py --tables        # 테이블 생성")

    if empty_count > 0:
        print(f"\n  {BOLD}다음 단계:{NC}")
        print(f"    uv run python scripts/setup.py --materialize   # 데이터 적재")

    if missing == 0 and empty_count == 0:
        print(f"\n  {GREEN}{BOLD}모든 테이블에 데이터가 적재되어 있습니다.{NC}")


# ─────────────────────────────────────────────────────────────────────────────────
# 뷰 생성
# ─────────────────────────────────────────────────────────────────────────────────
def ensure_views() -> None:
    """SQL 뷰를 생성/갱신한다."""
    header("6. SQL 뷰 생성")

    conn = get_pg_conn()
    if not conn:
        return

    sql_dir = ROOT / "sql" / "marts"
    if not sql_dir.exists():
        skip("sql/marts/ 디렉토리 없음")
        conn.close()
        return

    from dagster_project.resources.settings_store import SettingsStoreResource
    store = SettingsStoreResource()

    # 뷰 SQL 파일 처리
    view_files = {
        "v_top_resources_30d.sql": {
            "lookback_days": str(store.get_int("reporting.lookback_days", 30)),
            "top_resources_limit": str(store.get_int("reporting.top_resources_limit", 20)),
        },
        "v_variance.sql": {
            "variance_over_pct": str(store.get_float("variance.threshold.over_pct", 20.0)),
            "variance_under_pct": str(store.get_float("variance.threshold.under_pct", 20.0)),
        },
    }

    created = 0
    for filename, params in view_files.items():
        filepath = sql_dir / filename
        if not filepath.exists():
            continue
        sql = filepath.read_text()
        for key, val in params.items():
            sql = sql.replace(f"{{{{{key}}}}}", val)
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            ok(f"{filename}")
            created += 1
        except Exception as e:
            fail(f"{filename}: {e}")

    # dim_cost_unit view/table
    dcu = sql_dir / "dim_cost_unit.sql"
    if dcu.exists() and table_exists(conn, "fact_daily_cost"):
        try:
            with conn.cursor() as cur:
                cur.execute(dcu.read_text())
            ok("dim_cost_unit.sql")
            created += 1
        except Exception as e:
            fail(f"dim_cost_unit.sql: {e}")

    if created == 0:
        skip("뷰 파일 없거나 fact_daily_cost 비어있음")

    conn.close()


# ─────────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="FinOps Platform 개발환경 셋업",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  uv run python scripts/setup.py              # 상태 확인 + 테이블 생성 + 설정 시드
  uv run python scripts/setup.py --status     # 현재 상태만 확인
  uv run python scripts/setup.py --materialize # 데이터 적재 (비어있는 asset만)
  uv run python scripts/setup.py --all        # 전체 (테이블 + 시드 + 데이터 적재)
  uv run python scripts/setup.py --all --force # 전체 재실행 (이미 있어도 덮어쓰기)
""",
    )
    parser.add_argument("--status", action="store_true", help="현재 상태만 확인")
    parser.add_argument("--tables", action="store_true", help="테이블 생성만")
    parser.add_argument("--seed", action="store_true", help="설정/예산 시드만")
    parser.add_argument("--materialize", action="store_true", help="Dagster asset 실행 (데이터 적재)")
    parser.add_argument("--views", action="store_true", help="SQL 뷰 생성만")
    parser.add_argument("--all", action="store_true", help="전체 실행 (테이블 + 시드 + 뷰 + 데이터)")
    parser.add_argument("--force", action="store_true", help="이미 데이터 있어도 재실행")
    args = parser.parse_args()

    print(f"\n{BOLD}FinOps Platform Setup{NC}")
    print(f"{DIM}언제든 다시 실행하면 부족한 부분만 셋업합니다.{NC}")

    # --status: 상태만 보여주고 종료
    if args.status:
        show_status()
        return 0

    # 특정 단계만 지정
    specific = args.tables or args.seed or args.materialize or args.views
    run_all = args.all or (not specific)  # 아무 옵션 없으면 tables + seed 기본 실행

    # 1. 사전 조건
    prereqs = check_prerequisites()
    if not prereqs.get("pg"):
        fail("PostgreSQL 연결이 안 됩니다. DB를 먼저 시작하세요.")
        print(f"\n  {DIM}Linux:  sudo systemctl start postgresql{NC}")
        print(f"  {DIM}macOS:  brew services start postgresql{NC}")
        print(f"  {DIM}WSL2:   sudo service postgresql start{NC}")
        return 1

    # 2. 테이블
    if run_all or args.tables or args.all:
        ensure_all_tables()

    # 3~4. 설정 시드
    if run_all or args.seed or args.all:
        seed_settings()
        seed_budget()

    # 6. 뷰
    if args.views or args.all:
        ensure_views()

    # 5. 데이터 적재
    if args.materialize or args.all:
        materialize_assets(force=args.force)

    # 최종 상태
    show_status()

    return 0


if __name__ == "__main__":
    sys.exit(main())
