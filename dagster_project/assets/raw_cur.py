"""Raw CUR Asset — 가상 AWS CUR 생성 및 Pydantic 검증."""


from datetime import date

from dagster import AssetExecutionContext, MonthlyPartitionsDefinition, asset
from pydantic import ValidationError

from ..config import load_config
from ..generators.aws_cur_generator import AwsCurGenerator
from ..schemas.focus_v1 import FocusRecord

_cfg = load_config()
MONTHLY_PARTITIONS = MonthlyPartitionsDefinition(
    start_date=_cfg.dagster.partition_start_date
)


@asset(
    partitions_def=MONTHLY_PARTITIONS,
    description="가상 AWS CUR 데이터를 생성하고 FOCUS 1.0 Pydantic 스키마로 검증한다.",
    group_name="ingestion",
)
def raw_cur(context: AssetExecutionContext) -> list[FocusRecord]:
    """월별 파티션 키에 해당하는 FOCUS 1.0 레코드를 생성한다.

    AwsCurGenerator(seed=42)를 사용하여 결정론적 출력을 보장한다.
    모든 레코드는 FocusRecord Pydantic 모델로 검증된다.
    """
    partition_key = context.partition_key  # "2024-01-01"
    period_start = date.fromisoformat(partition_key)
    if period_start.month == 12:
        period_end = date(period_start.year + 1, 1, 1)
    else:
        period_end = date(period_start.year, period_start.month + 1, 1)

    context.log.info(f"Generating CUR for {period_start} ~ {period_end}")

    generator = AwsCurGenerator()
    records: list[FocusRecord] = []
    validation_errors = 0

    for record in generator.generate(period_start, period_end):
        try:
            # 생성기가 이미 FocusRecord를 반환하지만, 명시적으로 재검증
            validated = FocusRecord.model_validate(record.model_dump())
            records.append(validated)
        except ValidationError as exc:
            context.log.warning(f"Validation failed for {record.ResourceId}: {exc}")
            validation_errors += 1

    context.log.info(
        f"Generated {len(records)} records, {validation_errors} validation errors"
    )

    if validation_errors > 0:
        raise ValueError(f"{validation_errors} records failed Pydantic validation")

    return records
