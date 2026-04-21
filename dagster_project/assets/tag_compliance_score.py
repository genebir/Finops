"""tag_compliance_score asset — 팀·프로바이더별 태그 준수율 점수 계산."""

from datetime import datetime, timezone

import psycopg2.extras
from dagster import AssetExecutionContext, asset

from ..db_schema import ensure_tables
from ..resources.duckdb_io import DuckDBResource


@asset(
    deps=["resource_inventory", "tag_policy"],
    required_resource_keys={"duckdb_resource"},
    description="팀·프로바이더별 태그 준수율 점수(0-100)를 dim_tag_compliance에 저장한다.",
)
def tag_compliance_score(context: AssetExecutionContext) -> None:
    duckdb_resource: DuckDBResource = context.resources.duckdb_resource  # type: ignore[assignment]

    with duckdb_resource.get_connection() as conn:
        ensure_tables(conn, "dim_tag_compliance")

        with conn.cursor() as cur:
            # 최신 월 결정 (dim_resource_inventory 기준)
            cur.execute(
                "SELECT to_char(MAX(last_seen_date),'YYYY-MM') FROM dim_resource_inventory"
            )
            row = cur.fetchone()
            billing_month = row[0] if row and row[0] else "2024-01"

            # 팀·프로바이더별 리소스 수 + 태그 완성 수
            cur.execute(
                """
                SELECT provider, team,
                       COUNT(*)                              AS total_resources,
                       COUNT(*) FILTER (WHERE tags_complete) AS tagged_resources
                FROM dim_resource_inventory
                GROUP BY provider, team
                """
            )
            inventory_rows = cur.fetchall()

            # 팀·프로바이더별 위반 수 (당일 기준)
            cur.execute(
                """
                SELECT provider, COALESCE(team, 'unknown') AS team,
                       COUNT(*) AS violation_count
                FROM dim_tag_violations
                GROUP BY provider, team
                """
            )
            violation_rows = cur.fetchall()

        viol_map: dict[tuple[str, str], int] = {}
        for provider, team, cnt in violation_rows:
            viol_map[(provider, team)] = int(cnt)

        rows: list[tuple] = []
        for provider, team, total, tagged in inventory_rows:
            total_int = int(total)
            tagged_int = int(tagged)
            completeness = (tagged_int / total_int * 100.0) if total_int > 0 else 0.0
            viol_count = viol_map.get((provider, team), 0)
            # violation penalty: each violation docks up to 5 points, capped at 30
            viol_penalty = min(viol_count * 5.0, 30.0)
            score = max(0.0, round(completeness * 0.7 + (100.0 - completeness) * 0.3 - viol_penalty, 2))
            # simpler formula: 70% weight on completeness, violations as penalty
            score = round(min(100.0, completeness - viol_penalty * (1 - completeness / 100.0)), 2)
            score = max(0.0, score)
            rows.append((
                billing_month, team, provider,
                total_int, tagged_int, viol_count,
                round(completeness, 2), score,
                datetime.now(tz=timezone.utc),
            ))

        # rank by score descending
        rows.sort(key=lambda r: r[7], reverse=True)
        rows = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], idx + 1, r[8])
                for idx, r in enumerate(rows)]

        with duckdb_resource.get_connection() as conn2:
            with conn2.cursor() as cur2:
                cur2.execute(
                    "DELETE FROM dim_tag_compliance WHERE billing_month = %s",
                    (billing_month,),
                )
                if rows:
                    psycopg2.extras.execute_values(
                        cur2,
                        """
                        INSERT INTO dim_tag_compliance
                            (billing_month, team, provider, total_resources, tagged_resources,
                             violation_count, tag_completeness, compliance_score, rank, computed_at)
                        VALUES %s
                        """,
                        rows,
                    )

    context.log.info(
        "tag_compliance_score: month=%s rows=%d", billing_month, len(rows)
    )
