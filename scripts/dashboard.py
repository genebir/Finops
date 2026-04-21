"""FinOps 터미널 대시보드.

사용법:
    uv run python scripts/dashboard.py [--month 2026-03]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
from datetime import date

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dagster_project.config import load_config
from dagster_project.resources.duckdb_io import DuckDBResource

console = Console()
_cfg = load_config()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FinOps 터미널 대시보드")
    parser.add_argument(
        "--month",
        default=date.today().strftime("%Y-%m"),
        help="분석 대상 월 (기본값: 이번 달, 형식: YYYY-MM)",
    )
    return parser.parse_args()


def _provider_summary(duckdb: DuckDBResource, month_str: str) -> Table:
    table = Table(title="☁️  클라우드별 월간 비용", show_header=True, header_style="bold cyan")
    table.add_column("Provider", style="bold")
    table.add_column("Resources", justify="right")
    table.add_column("Total Cost ($)", justify="right", style="yellow")
    table.add_column("Avg Daily ($)", justify="right")

    with duckdb.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                provider,
                COUNT(DISTINCT resource_id)      AS resources,
                SUM(CAST(effective_cost AS DOUBLE PRECISION)) AS total_cost,
                SUM(CAST(effective_cost AS DOUBLE PRECISION))
                    / NULLIF(COUNT(DISTINCT charge_date), 0) AS avg_daily
            FROM fact_daily_cost
            WHERE to_char(charge_date, 'YYYY-MM') = %s
            GROUP BY provider
            ORDER BY total_cost DESC
            """,
            [month_str],
        )
        rows = cur.fetchall()
        cur.close()

    if not rows:
        table.add_row("[dim]데이터 없음[/dim]", "", "", "")
    else:
        for provider, resources, total, avg_daily in rows:
            table.add_row(
                str(provider),
                str(resources),
                f"{float(total):,.2f}",
                f"{float(avg_daily):,.2f}",
            )
    return table


def _top_resources(duckdb: DuckDBResource, month_str: str, limit: int = 10) -> Table:
    table = Table(title=f"💸 Top {limit} Resources (월간 비용)", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Resource ID", no_wrap=True)
    table.add_column("Provider", style="dim")
    table.add_column("Service", style="dim")
    table.add_column("Team")
    table.add_column("Cost ($)", justify="right", style="yellow bold")

    with duckdb.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                resource_id,
                provider,
                service_name,
                team,
                SUM(CAST(effective_cost AS DOUBLE PRECISION)) AS total_cost
            FROM fact_daily_cost
            WHERE to_char(charge_date, 'YYYY-MM') = %s
            GROUP BY resource_id, provider, service_name, team
            ORDER BY total_cost DESC
            LIMIT %s
            """,
            [month_str, limit],
        )
        rows = cur.fetchall()
        cur.close()

    if not rows:
        table.add_row("", "[dim]데이터 없음[/dim]", "", "", "", "")
    else:
        for i, (res_id, provider, service, team, cost) in enumerate(rows, 1):
            table.add_row(
                str(i),
                str(res_id),
                str(provider),
                str(service or ""),
                str(team or ""),
                f"{float(cost):,.2f}",
            )
    return table


def _anomaly_summary(duckdb: DuckDBResource, month_str: str, limit: int = 10) -> Table:
    table = Table(title="🚨 최근 이상치 (Critical 우선)", show_header=True, header_style="bold cyan")
    table.add_column("Severity", justify="center")
    table.add_column("Detector", style="dim")
    table.add_column("Resource ID")
    table.add_column("Date")
    table.add_column("Cost ($)", justify="right", style="yellow")
    table.add_column("Mean ($)", justify="right", style="dim")
    table.add_column("Z-Score", justify="right")

    with duckdb.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='anomaly_scores'"
        )
        if not cur.fetchone():
            cur.close()
            table.add_row("[dim]anomaly_scores 없음[/dim]", "", "", "", "", "", "")
            return table

        cur.execute(
            """
            SELECT
                severity,
                detector_name,
                resource_id,
                charge_date::TEXT,
                CAST(effective_cost AS DOUBLE PRECISION),
                CAST(mean_cost AS DOUBLE PRECISION),
                CAST(z_score AS DOUBLE PRECISION)
            FROM anomaly_scores
            WHERE to_char(charge_date, 'YYYY-MM') = %s
            ORDER BY
                CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                ABS(z_score) DESC
            LIMIT %s
            """,
            [month_str, limit],
        )
        rows = cur.fetchall()
        cur.close()

    if not rows:
        table.add_row("[dim]이상치 없음[/dim]", "", "", "", "", "", "")
    else:
        for severity, detector, res_id, charge_date, cost, mean_cost, z_score in rows:
            sev_str = (
                Text("● CRITICAL", style="bold red")
                if severity == "critical"
                else Text("● warning", style="yellow")
            )
            table.add_row(
                sev_str,
                str(detector or "zscore"),
                str(res_id),
                str(charge_date),
                f"{float(cost):,.2f}",
                f"{float(mean_cost):,.2f}",
                f"{float(z_score):+.2f}",
            )
    return table


def _prophet_forecast_summary(duckdb: DuckDBResource, limit: int = 8) -> Table:
    table = Table(title="🔮 Prophet 예측 (Top 비용)", show_header=True, header_style="bold cyan")
    table.add_column("Resource ID")
    table.add_column("Predicted/월 ($)", justify="right", style="yellow")
    table.add_column("Lower ($)", justify="right", style="dim")
    table.add_column("Upper ($)", justify="right", style="dim")
    table.add_column("Actual/월 ($)", justify="right")
    table.add_column("Status")

    with duckdb.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='dim_forecast_variance_prophet'"
        )
        if not cur.fetchone():
            cur.close()
            table.add_row("[dim]dim_forecast_variance_prophet 없음[/dim]", "", "", "", "", "")
            return table

        cur.execute(
            """
            SELECT
                resource_id,
                CAST(predicted_monthly_cost AS DOUBLE PRECISION),
                CAST(lower_bound_monthly_cost AS DOUBLE PRECISION),
                CAST(upper_bound_monthly_cost AS DOUBLE PRECISION),
                CAST(actual_monthly_cost AS DOUBLE PRECISION),
                status
            FROM dim_forecast_variance_prophet
            ORDER BY predicted_monthly_cost DESC
            LIMIT %s
            """,
            [limit],
        )
        rows = cur.fetchall()
        cur.close()

    if not rows:
        table.add_row("[dim]예측 데이터 없음[/dim]", "", "", "", "", "")
    else:
        status_style = {
            "within_bounds": "green",
            "above_upper": "red",
            "below_lower": "blue",
            "no_actual": "dim",
        }
        for res_id, predicted, lower, upper, actual, status in rows:
            style = status_style.get(str(status), "")
            table.add_row(
                str(res_id),
                f"{float(predicted):,.2f}",
                f"{float(lower):,.2f}",
                f"{float(upper):,.2f}",
                f"{float(actual):,.2f}",
                Text(str(status), style=style),
            )
    return table


def main() -> None:
    args = _parse_args()
    month_str = args.month

    duckdb = DuckDBResource()

    console.rule(f"[bold cyan]FinOps Dashboard[/bold cyan]  [{month_str}]")
    console.print()

    try:
        with duckdb.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM fact_daily_cost LIMIT 1")
            cur.close()
        has_data = True
    except Exception:
        has_data = False

    if not has_data:
        console.print(Panel(
            "[yellow]fact_daily_cost 테이블이 없거나 비어 있습니다.\n"
            "먼저 Dagster 파이프라인을 실행하세요:[/yellow]\n\n"
            "  uv run dagster dev",
            title="데이터 없음",
            border_style="yellow",
        ))
        return

    console.print(_provider_summary(duckdb, month_str))
    console.print()
    console.print(_top_resources(duckdb, month_str))
    console.print()
    console.print(_anomaly_summary(duckdb, month_str))
    console.print()
    console.print(_prophet_forecast_summary(duckdb))
    console.print()
    console.rule("[dim]data/reports/ 폴더에서 CSV 보고서를 확인하세요[/dim]")


if __name__ == "__main__":
    main()
