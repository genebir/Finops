"""FX Rates Asset — 환율 정보를 dim_fx_rates 테이블에 저장한다."""

from dagster import AssetExecutionContext, asset

from ..providers.static_fx_provider import StaticFxProvider
from ..resources.duckdb_io import DuckDBResource
from .raw_cur import MONTHLY_PARTITIONS

_CREATE_FX_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dim_fx_rates (
    base_currency   VARCHAR NOT NULL,
    target_currency VARCHAR NOT NULL,
    rate            DECIMAL(18, 6) NOT NULL,
    effective_date  DATE NOT NULL,
    source          VARCHAR NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (base_currency, target_currency, effective_date)
)
"""


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    description=(
        "정적 환율 데이터를 dim_fx_rates 테이블에 저장한다. "
        "USD 기준 EUR, GBP, KRW, JPY 등 주요 통화 환율을 제공한다. "
        "Phase 6에서 실시간 API 연동으로 교체 가능하다."
    ),
    group_name="reference",
)
def fx_rates(
    context: AssetExecutionContext,
    duckdb_resource: DuckDBResource,
) -> None:
    """환율 참조 데이터를 DuckDB dim_fx_rates에 저장한다.

    StaticFxProvider로부터 USD 기준 환율을 가져와 테이블에 upsert한다.
    """
    provider = StaticFxProvider()
    rates = provider.get_all_rates(base="USD")
    context.log.info(f"Loaded {len(rates)} FX rates from StaticFxProvider")

    with duckdb_resource.get_connection() as conn:
        conn.execute(_CREATE_FX_TABLE_SQL)
        conn.execute("DELETE FROM dim_fx_rates WHERE base_currency = 'USD'")

        for rate in rates:
            conn.execute(
                """
                INSERT INTO dim_fx_rates
                    (base_currency, target_currency, rate, effective_date, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    rate.base_currency,
                    rate.target_currency,
                    float(rate.rate),
                    rate.effective_date.isoformat(),
                    rate.source,
                ],
            )

        count = conn.execute("SELECT COUNT(*) FROM dim_fx_rates").fetchone()
        context.log.info(f"dim_fx_rates: {count[0] if count else 0}개 환율 저장")
