"""FX Rates Asset — 환율 정보를 dim_fx_rates 테이블에 저장한다."""

from dagster import AssetExecutionContext, asset

from ..db_schema import ensure_tables
from ..providers.static_fx_provider import StaticFxProvider
from ..resources.duckdb_io import DuckDBResource
from .raw_cur import MONTHLY_PARTITIONS


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    description=(
        "정적 환율 데이터를 dim_fx_rates 테이블에 저장한다. "
        "USD 기준 EUR, GBP, KRW, JPY 등 주요 통화 환율을 제공한다."
    ),
    group_name="reference",
)
def fx_rates(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
) -> None:
    """환율 참조 데이터를 PostgreSQL dim_fx_rates에 저장한다."""
    provider = StaticFxProvider()
    rates = provider.get_all_rates(base="USD")
    context.log.info(f"Loaded {len(rates)} FX rates from StaticFxProvider")

    with duckdb_resource.get_connection() as conn:
        ensure_tables(conn, "dim_fx_rates")
        cur = conn.cursor()
        cur.execute("DELETE FROM dim_fx_rates WHERE base_currency = 'USD'")

        for rate in rates:
            cur.execute(
                """
                INSERT INTO dim_fx_rates
                    (base_currency, target_currency, rate, effective_date, source)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    rate.base_currency,
                    rate.target_currency,
                    float(rate.rate),
                    rate.effective_date.isoformat(),
                    rate.source,
                ],
            )

        cur.execute("SELECT COUNT(*) FROM dim_fx_rates")
        count = cur.fetchone()
        context.log.info(f"dim_fx_rates: {count[0] if count else 0}개 환율 저장")
        cur.close()
