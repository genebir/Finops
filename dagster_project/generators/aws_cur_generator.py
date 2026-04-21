"""AwsCurGenerator — 가상 AWS CUR 생성기 (CostSource 구현체)."""

from __future__ import annotations

import os
import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from ..core.cost_unit import CostUnit
from ..schemas.focus_v1 import ChargeCategory, FocusRecord, ServiceCategory

_BILLING_ACCOUNT_ID = "123456789012"
_SUB_ACCOUNT_ID = "987654321098"

_REGIONS = [
    ("us-east-1", "US East (N. Virginia)", "us-east-1a"),
    ("us-east-1", "US East (N. Virginia)", "us-east-1b"),
    ("us-west-2", "US West (Oregon)", "us-west-2a"),
    ("eu-west-1", "EU West (Ireland)", "eu-west-1a"),
]

_TEAMS = ["platform", "data", "ml", "frontend"]
_PRODUCTS = ["checkout", "search", "recommender", "api"]
_ENVS = ["prod", "prod", "prod", "staging", "staging", "dev"]  # prod 가중치


@dataclass(frozen=True)
class _ResourceDef:
    resource_type: str
    resource_name: str
    service_name: str
    service_category: ServiceCategory
    base_daily_cost: Decimal
    tags: dict[str, str]
    region_id: str
    region_name: str
    availability_zone: str
    usage_unit: str
    sku_id: str
    is_anomaly: bool = False

    @property
    def resource_id(self) -> str:
        return f"{self.resource_type}.{self.resource_name}"

    @property
    def cost_unit(self) -> CostUnit:
        return CostUnit.from_tags(self.tags)


# terraform/sample/main.tf 과 ResourceId가 반드시 일치해야 함 (Step 10)
_TERRAFORM_RESOURCES: list[_ResourceDef] = [
    _ResourceDef(
        resource_type="aws_instance",
        resource_name="web_1",
        service_name="Amazon EC2",
        service_category=ServiceCategory.Compute,
        base_daily_cost=Decimal("8.500000"),
        tags={"team": "platform", "product": "checkout", "env": "prod"},
        region_id="us-east-1",
        region_name="US East (N. Virginia)",
        availability_zone="us-east-1a",
        usage_unit="Hrs",
        sku_id="EC2-INSTANCE-T3-MEDIUM",
    ),
    _ResourceDef(
        resource_type="aws_instance",
        resource_name="web_2",
        service_name="Amazon EC2",
        service_category=ServiceCategory.Compute,
        base_daily_cost=Decimal("8.500000"),
        tags={"team": "platform", "product": "checkout", "env": "prod"},
        region_id="us-east-1",
        region_name="US East (N. Virginia)",
        availability_zone="us-east-1b",
        usage_unit="Hrs",
        sku_id="EC2-INSTANCE-T3-MEDIUM",
    ),
    _ResourceDef(
        resource_type="aws_instance",
        resource_name="api_1",
        service_name="Amazon EC2",
        service_category=ServiceCategory.Compute,
        base_daily_cost=Decimal("6.200000"),
        tags={"team": "data", "product": "api", "env": "prod"},
        region_id="us-east-1",
        region_name="US East (N. Virginia)",
        availability_zone="us-east-1a",
        usage_unit="Hrs",
        sku_id="EC2-INSTANCE-T3-SMALL",
    ),
    _ResourceDef(
        resource_type="aws_instance",
        resource_name="api_2",
        service_name="Amazon EC2",
        service_category=ServiceCategory.Compute,
        base_daily_cost=Decimal("6.200000"),
        tags={"team": "data", "product": "api", "env": "prod"},
        region_id="us-west-2",
        region_name="US West (Oregon)",
        availability_zone="us-west-2a",
        usage_unit="Hrs",
        sku_id="EC2-INSTANCE-T3-SMALL",
    ),
    _ResourceDef(
        resource_type="aws_instance",
        resource_name="ml_1",
        service_name="Amazon EC2",
        service_category=ServiceCategory.Compute,
        base_daily_cost=Decimal("24.000000"),
        tags={"team": "ml", "product": "recommender", "env": "prod"},
        region_id="us-east-1",
        region_name="US East (N. Virginia)",
        availability_zone="us-east-1a",
        usage_unit="Hrs",
        sku_id="EC2-INSTANCE-G4DN-XLARGE",
    ),
    _ResourceDef(
        resource_type="aws_db_instance",
        resource_name="main_1",
        service_name="Amazon RDS",
        service_category=ServiceCategory.Database,
        base_daily_cost=Decimal("18.000000"),
        tags={"team": "platform", "product": "checkout", "env": "prod"},
        region_id="us-east-1",
        region_name="US East (N. Virginia)",
        availability_zone="us-east-1a",
        usage_unit="Hrs",
        sku_id="RDS-MYSQL-DB-T3-MEDIUM",
    ),
    _ResourceDef(
        resource_type="aws_db_instance",
        resource_name="analytics_1",
        service_name="Amazon RDS",
        service_category=ServiceCategory.Database,
        base_daily_cost=Decimal("14.000000"),
        tags={"team": "data", "product": "search", "env": "prod"},
        region_id="us-east-1",
        region_name="US East (N. Virginia)",
        availability_zone="us-east-1b",
        usage_unit="Hrs",
        sku_id="RDS-POSTGRES-DB-T3-MEDIUM",
    ),
    _ResourceDef(
        resource_type="aws_s3_bucket",
        resource_name="assets_1",
        service_name="Amazon S3",
        service_category=ServiceCategory.Storage,
        base_daily_cost=Decimal("0.480000"),
        tags={"team": "frontend", "product": "checkout", "env": "prod"},
        region_id="us-east-1",
        region_name="US East (N. Virginia)",
        availability_zone="us-east-1a",
        usage_unit="GB-Mo",
        sku_id="S3-STORAGE-STANDARD",
    ),
    _ResourceDef(
        resource_type="aws_s3_bucket",
        resource_name="assets_2",
        service_name="Amazon S3",
        service_category=ServiceCategory.Storage,
        base_daily_cost=Decimal("0.320000"),
        tags={"team": "data", "product": "search", "env": "prod"},
        region_id="us-east-1",
        region_name="US East (N. Virginia)",
        availability_zone="us-east-1a",
        usage_unit="GB-Mo",
        sku_id="S3-STORAGE-STANDARD",
    ),
    _ResourceDef(
        resource_type="aws_s3_bucket",
        resource_name="assets_3",
        service_name="Amazon S3",
        service_category=ServiceCategory.Storage,
        base_daily_cost=Decimal("0.250000"),
        tags={"team": "platform", "product": "checkout", "env": "prod"},
        region_id="us-east-1",
        region_name="US East (N. Virginia)",
        availability_zone="us-east-1a",
        usage_unit="GB-Mo",
        sku_id="S3-STORAGE-STANDARD",
    ),
]

# 추가 랜덤 리소스 생성용 서비스 풀 (가중치, type, service, category, daily_cost_range, usage_unit)
_EXTRA_SERVICE_POOL = [
    (40, "aws_instance", "Amazon EC2", ServiceCategory.Compute, (2.0, 15.0), "Hrs", "EC2-INSTANCE-T3"),
    (20, "aws_db_instance", "Amazon RDS", ServiceCategory.Database, (5.0, 30.0), "Hrs", "RDS-DB-T3"),
    (15, "aws_s3_bucket", "Amazon S3", ServiceCategory.Storage, (0.1, 2.0), "GB-Mo", "S3-STORAGE"),
    (10, "aws_lambda_function", "AWS Lambda", ServiceCategory.Compute, (0.01, 0.5), "GB-Second", "LAMBDA-GB-SEC"),
    (15, "aws_elasticache_cluster", "Amazon ElastiCache", ServiceCategory.Database, (1.0, 8.0), "Hrs", "ELASTICACHE-T3"),
]


def _weighted_choice(rng: random.Random, pool: list[tuple[int, object]], *, key: int = 0) -> object:
    total = sum(item[key] for item in pool)  # type: ignore[index]
    r = rng.uniform(0, total)
    cumulative = 0.0
    for item in pool:
        cumulative += item[key]  # type: ignore[index]
        if r <= cumulative:
            return item
    return pool[-1]


def _build_extra_resources(rng: random.Random, count: int) -> list[_ResourceDef]:
    resources: list[_ResourceDef] = []
    anomaly_indices = set(rng.sample(range(count), k=min(2, count)))

    for i in range(count):
        entry = _weighted_choice(rng, _extra_service_pool_tuples(), key=0)  # type: ignore[arg-type]
        weight, rtype, sname, scat, cost_range, uunit, sku = entry  # type: ignore[misc]
        low, high = cost_range
        base_cost = Decimal(str(round(rng.uniform(low, high), 6)))

        is_anomaly = i in anomaly_indices
        if is_anomaly:
            # 평균 대비 5~8배 이상치
            base_cost = base_cost * Decimal(str(round(rng.uniform(5.0, 8.0), 2)))

        region_id, region_name, az = rng.choice(_REGIONS)
        tags = {
            "team": rng.choice(_TEAMS),
            "product": rng.choice(_PRODUCTS),
            "env": rng.choice(_ENVS),
        }
        suffix = f"extra_{i + 1}"
        resources.append(
            _ResourceDef(
                resource_type=str(rtype),
                resource_name=suffix,
                service_name=str(sname),
                service_category=scat,  # type: ignore[arg-type]
                base_daily_cost=base_cost,
                tags=tags,
                region_id=region_id,
                region_name=region_name,
                availability_zone=az,
                usage_unit=str(uunit),
                sku_id=f"{sku}-EXTRA-{i + 1}",
                is_anomaly=is_anomaly,
            )
        )
    return resources


def _extra_service_pool_tuples() -> list[tuple[int, str, str, ServiceCategory, tuple[float, float], str, str]]:
    return _EXTRA_SERVICE_POOL  # type: ignore[return-value]


def _make_charge_record(
    rng: random.Random,
    res: _ResourceDef,
    day: date,
    billing_period_start: datetime,
    billing_period_end: datetime,
) -> FocusRecord:
    charge_start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=UTC)
    charge_end = charge_start + timedelta(hours=24)

    # 일별 비용: base ± 15% 변동
    variation = Decimal(str(round(rng.uniform(0.85, 1.15), 6)))
    effective_cost = (res.base_daily_cost * variation).quantize(Decimal("0.000001"))
    list_cost = (effective_cost * Decimal("1.15")).quantize(Decimal("0.000001"))
    billed_cost = effective_cost
    contracted_cost = effective_cost

    usage_qty = Decimal("24.000000") if res.usage_unit == "Hrs" else Decimal("1.000000")

    return FocusRecord(
        BillingAccountId=_BILLING_ACCOUNT_ID,
        SubAccountId=_SUB_ACCOUNT_ID,
        ResourceId=res.resource_id,
        ResourceName=res.resource_name,
        ResourceType=res.resource_type,
        ChargePeriodStart=charge_start,
        ChargePeriodEnd=charge_end,
        BillingPeriodStart=billing_period_start,
        BillingPeriodEnd=billing_period_end,
        BilledCost=billed_cost,
        EffectiveCost=effective_cost,
        ListCost=list_cost,
        ContractedCost=contracted_cost,
        BillingCurrency="USD",
        ServiceName=res.service_name,
        ServiceCategory=res.service_category,
        ProviderName="AWS",
        RegionId=res.region_id,
        RegionName=res.region_name,
        AvailabilityZone=res.availability_zone,
        ChargeCategory=ChargeCategory.Usage,
        ChargeDescription=f"{res.service_name} {res.resource_type} usage",
        UsageQuantity=usage_qty,
        UsageUnit=res.usage_unit,
        PricingQuantity=usage_qty,
        PricingUnit=res.usage_unit,
        SkuId=res.sku_id,
        Tags=res.tags,
    )


class AwsCurGenerator:
    """가상 AWS CUR 생성기.

    Seeded random으로 동일 입력 → 동일 출력을 보장한다.
    terraform/sample/main.tf 의 리소스 주소와 ResourceId가 일치하도록 설계되어
    Infracost 예측과 LEFT JOIN이 가능하다.
    """

    name: str = "aws"
    resource_id_strategy: str = "terraform_address"

    def __init__(self, seed: int | None = None) -> None:
        env_seed = os.environ.get("CUR_SEED")
        self._seed = int(env_seed) if env_seed is not None else (seed if seed is not None else 42)

    def generate(self, period_start: date, period_end: date) -> Iterator[FocusRecord]:
        """period_start ~ period_end(미포함) 기간의 FOCUS 레코드를 yield."""
        rng = random.Random(self._seed)

        extra_count = rng.randint(5, 20)
        extra_resources = _build_extra_resources(rng, extra_count)
        all_resources = _TERRAFORM_RESOURCES + extra_resources

        billing_period_start = datetime(period_start.year, period_start.month, 1, tzinfo=UTC)
        if period_start.month == 12:
            billing_period_end = datetime(period_start.year + 1, 1, 1, tzinfo=UTC)
        else:
            billing_period_end = datetime(period_start.year, period_start.month + 1, 1, tzinfo=UTC)

        current = period_start
        while current < period_end:
            for res in all_resources:
                yield _make_charge_record(rng, res, current, billing_period_start, billing_period_end)
            current += timedelta(days=1)
