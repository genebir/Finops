"""GcpBillingGenerator — 가상 GCP 빌링 생성기 (CostSource 구현체)."""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from ..config import load_config
from ..core.cost_unit import CostUnit
from ..schemas.focus_v1 import ChargeCategory, FocusRecord, ServiceCategory

_cfg = load_config()

_REGIONS = [
    ("us-central1",  "US Central (Iowa)",    None),
    ("us-east1",     "US East (S. Carolina)", None),
    ("europe-west1", "EU West (Belgium)",     None),
    ("asia-east1",   "Asia East (Taiwan)",    None),
]

_TEAMS    = ["platform", "data", "ml", "frontend"]
_PRODUCTS = ["checkout", "search", "recommender", "api"]
_ENVS     = ["prod", "prod", "prod", "staging", "staging", "dev"]


@dataclass(frozen=True)
class _GcpResourceDef:
    resource_type: str
    resource_name: str
    service_name: str
    service_category: ServiceCategory
    base_daily_cost: Decimal
    tags: dict[str, str]
    region_id: str
    region_name: str
    usage_unit: str
    sku_id: str
    is_anomaly: bool = False

    @property
    def resource_id(self) -> str:
        return f"{self.resource_type}.{self.resource_name}"

    @property
    def cost_unit(self) -> CostUnit:
        return CostUnit.from_tags(self.tags)


_FIXED_RESOURCES: list[_GcpResourceDef] = [
    _GcpResourceDef(
        resource_type="google_compute_instance",
        resource_name="web_1",
        service_name="Compute Engine",
        service_category=ServiceCategory.Compute,
        base_daily_cost=Decimal("7.200000"),
        tags={"team": "platform", "product": "checkout", "env": "prod"},
        region_id="us-central1",
        region_name="US Central (Iowa)",
        usage_unit="Hrs",
        sku_id="GCE-N1-STANDARD-2",
    ),
    _GcpResourceDef(
        resource_type="google_compute_instance",
        resource_name="api_1",
        service_name="Compute Engine",
        service_category=ServiceCategory.Compute,
        base_daily_cost=Decimal("5.400000"),
        tags={"team": "data", "product": "api", "env": "prod"},
        region_id="us-east1",
        region_name="US East (S. Carolina)",
        usage_unit="Hrs",
        sku_id="GCE-N1-STANDARD-1",
    ),
    _GcpResourceDef(
        resource_type="google_sql_database_instance",
        resource_name="main_1",
        service_name="Cloud SQL",
        service_category=ServiceCategory.Database,
        base_daily_cost=Decimal("12.000000"),
        tags={"team": "platform", "product": "checkout", "env": "prod"},
        region_id="us-central1",
        region_name="US Central (Iowa)",
        usage_unit="Hrs",
        sku_id="CLOUDSQL-POSTGRES-DB-N1-STANDARD-2",
    ),
    _GcpResourceDef(
        resource_type="google_storage_bucket",
        resource_name="assets_1",
        service_name="Cloud Storage",
        service_category=ServiceCategory.Storage,
        base_daily_cost=Decimal("0.360000"),
        tags={"team": "frontend", "product": "checkout", "env": "prod"},
        region_id="us-central1",
        region_name="US Central (Iowa)",
        usage_unit="GiB-Mo",
        sku_id="GCS-STANDARD-STORAGE",
    ),
    _GcpResourceDef(
        resource_type="google_bigquery_dataset",
        resource_name="analytics_1",
        service_name="BigQuery",
        service_category=ServiceCategory.Database,
        base_daily_cost=Decimal("8.500000"),
        tags={"team": "data", "product": "search", "env": "prod"},
        region_id="us-central1",
        region_name="US Central (Iowa)",
        usage_unit="TB",
        sku_id="BQ-ANALYSIS",
    ),
    _GcpResourceDef(
        resource_type="google_cloudfunctions_function",
        resource_name="handler_1",
        service_name="Cloud Functions",
        service_category=ServiceCategory.Compute,
        base_daily_cost=Decimal("0.150000"),
        tags={"team": "ml", "product": "recommender", "env": "prod"},
        region_id="us-central1",
        region_name="US Central (Iowa)",
        usage_unit="Invocations",
        sku_id="CF-INVOCATIONS",
    ),
]

_EXTRA_SERVICE_POOL: list[
    tuple[int, str, str, ServiceCategory, tuple[float, float], str, str]
] = [
    (35, "google_compute_instance",        "Compute Engine",   ServiceCategory.Compute,  (1.5, 12.0), "Hrs",         "GCE-N1"),
    (20, "google_sql_database_instance",   "Cloud SQL",        ServiceCategory.Database, (4.0, 20.0), "Hrs",         "CLOUDSQL"),
    (15, "google_storage_bucket",          "Cloud Storage",    ServiceCategory.Storage,  (0.1, 1.5),  "GiB-Mo",      "GCS"),
    (15, "google_bigquery_dataset",        "BigQuery",         ServiceCategory.Database, (1.0, 15.0), "TB",          "BQ"),
    (15, "google_cloudfunctions_function", "Cloud Functions",  ServiceCategory.Compute,  (0.01, 0.5), "Invocations", "CF"),
]


def _build_extra_resources(rng: random.Random, count: int) -> list[_GcpResourceDef]:
    resources: list[_GcpResourceDef] = []
    anomaly_indices = set(rng.sample(range(count), k=min(2, count)))

    for i in range(count):
        total = sum(w for w, *_ in _EXTRA_SERVICE_POOL)
        r = rng.uniform(0, total)
        cum = 0.0
        entry = _EXTRA_SERVICE_POOL[-1]
        for item in _EXTRA_SERVICE_POOL:
            cum += item[0]
            if r <= cum:
                entry = item
                break
        _, rtype, sname, scat, cost_range, uunit, sku = entry
        low, high = cost_range
        base_cost = Decimal(str(round(rng.uniform(low, high), 6)))

        is_anomaly = i in anomaly_indices
        if is_anomaly:
            base_cost = base_cost * Decimal(
                str(round(rng.uniform(
                    _cfg.gcp_generator.anomaly_multiplier_low,
                    _cfg.gcp_generator.anomaly_multiplier_high,
                ), 2))
            )

        region_id, region_name, _ = rng.choice(_REGIONS)
        tags = {
            "team": rng.choice(_TEAMS),
            "product": rng.choice(_PRODUCTS),
            "env": rng.choice(_ENVS),
        }
        resources.append(
            _GcpResourceDef(
                resource_type=str(rtype),
                resource_name=f"extra_{i + 1}",
                service_name=str(sname),
                service_category=scat,
                base_daily_cost=base_cost,
                tags=tags,
                region_id=region_id,
                region_name=region_name,
                usage_unit=str(uunit),
                sku_id=f"{sku}-EXTRA-{i + 1}",
                is_anomaly=is_anomaly,
            )
        )
    return resources


def _make_charge_record(
    rng: random.Random,
    res: _GcpResourceDef,
    day: date,
    billing_period_start: datetime,
    billing_period_end: datetime,
) -> FocusRecord:
    charge_start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=UTC)
    charge_end = charge_start + timedelta(hours=24)

    variation = Decimal(str(round(rng.uniform(
        _cfg.gcp_generator.cost_variation_low,
        _cfg.gcp_generator.cost_variation_high,
    ), 6)))
    effective_cost = (res.base_daily_cost * variation).quantize(Decimal("0.000001"))
    list_cost = (effective_cost * Decimal(str(_cfg.gcp_generator.list_price_markup))).quantize(
        Decimal("0.000001")
    )
    usage_qty = Decimal("24.000000") if res.usage_unit == "Hrs" else Decimal("1.000000")

    return FocusRecord(
        BillingAccountId=_cfg.gcp_generator.billing_account_id,
        SubAccountId=_cfg.gcp_generator.sub_account_id,
        ResourceId=res.resource_id,
        ResourceName=res.resource_name,
        ResourceType=res.resource_type,
        ChargePeriodStart=charge_start,
        ChargePeriodEnd=charge_end,
        BillingPeriodStart=billing_period_start,
        BillingPeriodEnd=billing_period_end,
        BilledCost=effective_cost,
        EffectiveCost=effective_cost,
        ListCost=list_cost,
        ContractedCost=effective_cost,
        BillingCurrency="USD",
        ServiceName=res.service_name,
        ServiceCategory=res.service_category,
        ProviderName="Google Cloud",
        RegionId=res.region_id,
        RegionName=res.region_name,
        AvailabilityZone=None,
        ChargeCategory=ChargeCategory.Usage,
        ChargeDescription=f"{res.service_name} {res.resource_type} usage",
        UsageQuantity=usage_qty,
        UsageUnit=res.usage_unit,
        PricingQuantity=usage_qty,
        PricingUnit=res.usage_unit,
        SkuId=res.sku_id,
        Tags=res.tags,
    )


class GcpBillingGenerator:
    """가상 GCP 빌링 생성기.

    Seeded random으로 동일 입력 → 동일 출력을 보장한다.
    CostSource Protocol을 준수한다.
    """

    name: str = "gcp"
    resource_id_strategy: str = "terraform_address"

    def __init__(self, seed: int | None = None) -> None:
        self._seed = seed if seed is not None else _cfg.gcp_generator.seed

    def generate(self, period_start: date, period_end: date) -> Iterator[FocusRecord]:
        """period_start ~ period_end(미포함) 기간의 GCP FOCUS 레코드를 yield."""
        rng = random.Random(self._seed)

        extra_count = rng.randint(
            _cfg.gcp_generator.extra_resources_min,
            _cfg.gcp_generator.extra_resources_max,
        )
        extra_resources = _build_extra_resources(rng, extra_count)
        all_resources = _FIXED_RESOURCES + extra_resources

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
