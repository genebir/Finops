"""Raw CUR Azure Asset — 가상 Azure 빌링 생성 및 Pydantic 검증."""


from datetime import date

from dagster import AssetExecutionContext, asset
from pydantic import ValidationError

from ..generators.azure_cost_generator import AzureCostGenerator
from ..schemas.focus_v1 import FocusRecord
from .raw_cur import MONTHLY_PARTITIONS


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    description="가상 Azure 빌링 데이터를 생성하고 FOCUS 1.0 Pydantic 스키마로 검증한다.",
    group_name="ingestion",
)
def raw_cur_azure(context: AssetExecutionContext) -> list[FocusRecord]:
    """월별 파티션 키에 해당하는 Azure FOCUS 1.0 레코드를 생성한다.

    AzureCostGenerator(seed=126)를 사용하여 결정론적 출력을 보장한다.
    """
    partition_key = context.partition_key
    period_start = date.fromisoformat(partition_key)
    if period_start.month == 12:
        period_end = date(period_start.year + 1, 1, 1)
    else:
        period_end = date(period_start.year, period_start.month + 1, 1)

    context.log.info(f"[Azure] Generating billing for {period_start} ~ {period_end}")

    generator = AzureCostGenerator()
    records: list[FocusRecord] = []
    validation_errors = 0

    for record in generator.generate(period_start, period_end):
        try:
            validated = FocusRecord.model_validate(record.model_dump())
            records.append(validated)
        except ValidationError as exc:
            context.log.warning(f"[Azure] Validation failed for {record.ResourceId}: {exc}")
            validation_errors += 1

    context.log.info(
        f"[Azure] Generated {len(records)} records, {validation_errors} validation errors"
    )

    if validation_errors > 0:
        raise ValueError(f"[Azure] {validation_errors} records failed Pydantic validation")

    return records
