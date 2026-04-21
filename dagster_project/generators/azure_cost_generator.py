"""AzureCostGenerator — 가상 Azure 빌링 생성기 (CostSource 구현체)."""

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
    ("eastus",        "East US",         "eastus-1"),
    ("westus2",       "West US 2",       "westus2-1"),
    ("northeurope",   "North Europe",    "northeurope-1"),
    ("southeastasia", "Southeast Asia",  "southeastasia-1"),
]

_TEAMS    = ["platform", "data", "ml", "frontend"]
_PRODUCTS = ["checkout", "search", "recommender", "api"]
_ENVS     = ["prod", "prod", "prod", "staging", "staging", "dev"]


@dataclass(frozen=True)
class _AzureResourceDef:
    resource_type: str
    resource_name: str
    service_name: str
    service_category: ServiceCategory
    base_daily_cost: Decimal
    tags: dict[str, str]
    region_id: str
    region_name: str
    availability_zone: str | None
    usage_unit: str
    sku_id: str
    is_anomaly: bool = False

    @property
    def resource_id(self) -> str:
        return f"{self.resource_type}.{self.resource_name}"

    @property
    def cost_unit(self) -> CostUnit:
        return CostUnit.from_tags(self.tags)


_FIXED_RESOURCES: list[_AzureResourceDef] = [
    _AzureResourceDef(
        resource_type="azurerm_virtual_machine",
        resource_name="web_1",
        service_name="Virtual Machines",
        service_category=ServiceCategory.Compute,
        base_daily_cost=Decimal("6.400000"),
        tags={"team": "platform", "product": "checkout", "env": "prod"},
        region_id="eastus",
        region_name="East US",
        availability_zone="eastus-1",
        usage_unit="Hrs",
        sku_id="AZ-VM-D2S-V3",
    ),
    _AzureResourceDef(
        resource_type="azurerm_virtual_machine",
        resource_name="api_1",
        service_name="Virtual Machines",
        service_category=ServiceCategory.Compute,
        base_daily_cost=Decimal("4.800000"),
        tags={"team": "data", "product": "api", "env": "prod"},
        region_id="westus2",
        region_name="West US 2",
        availability_zone="westus2-1",
        usage_unit="Hrs",
        sku_id="AZ-VM-D2S-V3",
    ),
    _AzureResourceDef(
        resource_type="azurerm_sql_database",
        resource_name="main_1",
        service_name="Azure SQL Database",
        service_category=ServiceCategory.Database,
        base_daily_cost=Decimal("11.000000"),
        tags={"team": "platform", "product": "checkout", "env": "prod"},
        region_id="eastus",
        region_name="East US",
        availability_zone=None,
        usage_unit="Hrs",
        sku_id="AZ-SQL-GP-GEN5-2",
    ),
    _AzureResourceDef(
        resource_type="azurerm_storage_account",
        resource_name="assets_1",
        service_name="Azure Blob Storage",
        service_category=ServiceCategory.Storage,
        base_daily_cost=Decimal("0.420000"),
        tags={"team": "frontend", "product": "checkout", "env": "prod"},
        region_id="eastus",
        region_name="East US",
        availability_zone=None,
        usage_unit="GiB-Mo",
        sku_id="AZ-BLOB-LRS",
    ),
    _AzureResourceDef(
        resource_type="azurerm_kubernetes_cluster",
        resource_name="ml_cluster_1",
        service_name="Azure Kubernetes Service",
        service_category=ServiceCategory.Compute,
        base_daily_cost=Decimal("18.000000"),
        tags={"team": "ml", "product": "recommender", "env": "prod"},
        region_id="eastus",
        region_name="East US",
        availability_zone="eastus-1",
        usage_unit="Hrs",
        sku_id="AZ-AKS-D4S-V3",
    ),
    _AzureResourceDef(
        resource_type="azurerm_redis_cache",
        resource_name="session_1",
        service_name="Azure Cache for Redis",
        service_category=ServiceCategory.Database,
        base_daily_cost=Decimal("2.200000"),
        tags={"team": "platform", "product": "checkout", "env": "prod"},
        region_id="eastus",
        region_name="East US",
        availability_zone=None,
        usage_unit="Hrs",
        sku_id="AZ-REDIS-C1",
    ),
    _AzureResourceDef(
        resource_type="azurerm_cosmosdb_account",
        resource_name="analytics_1",
        service_name="Azure Cosmos DB",
        service_category=ServiceCategory.Database,
        base_daily_cost=Decimal("9.500000"),
        tags={"team": "data", "product": "search", "env": "prod"},
        region_id="northeurope",
        region_name="North Europe",
        availability_zone=None,
        usage_unit="RU/s",
        sku_id="AZ-COSMOS-RU-400",
    ),
    _AzureResourceDef(
        resource_type="azurerm_function_app",
        resource_name="handler_1",
        service_name="Azure Functions",
        service_category=ServiceCategory.Compute,
        base_daily_cost=Decimal("0.180000"),
        tags={"team": "ml", "product": "recommender", "env": "prod"},
        region_id="eastus",
        region_name="East US",
        availability_zone=None,
        usage_unit="Executions",
        sku_id="AZ-FUNC-CONSUMPTION",
    ),
]

_EXTRA_SERVICE_POOL: list[
    tuple[int, str, str, ServiceCategory, tuple[float, float], str, str]
] = [
    (35, "azurerm_virtual_machine",      "Virtual Machines",           ServiceCategory.Compute,  (2.0, 14.0), "Hrs",        "AZ-VM"),
    (20, "azurerm_sql_database",         "Azure SQL Database",         ServiceCategory.Database, (4.0, 18.0), "Hrs",        "AZ-SQL"),
    (15, "azurerm_storage_account",      "Azure Blob Storage",         ServiceCategory.Storage,  (0.1, 2.0),  "GiB-Mo",     "AZ-BLOB"),
    (15, "azurerm_kubernetes_cluster",   "Azure Kubernetes Service",   ServiceCategory.Compute,  (5.0, 25.0), "Hrs",        "AZ-AKS"),
    (15, "azurerm_cosmosdb_account",     "Azure Cosmos DB",            ServiceCategory.Database, (1.0, 12.0), "RU/s",       "AZ-COSMOS"),
]


def _build_extra_resources(rng: random.Random, count: int) -> list[_AzureResourceDef]:
    resources: list[_AzureResourceDef] = []
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
                    _cfg.azure_generator.anomaly_multiplier_low,
                    _cfg.azure_generator.anomaly_multiplier_high,
                ), 2))
            )

        region_id, region_name, az = rng.choice(_REGIONS)
        tags = {
            "team": rng.choice(_TEAMS),
            "product": rng.choice(_PRODUCTS),
            "env": rng.choice(_ENVS),
        }
        resources.append(
            _AzureResourceDef(
                resource_type=str(rtype),
                resource_name=f"extra_{i + 1}",
                service_name=str(sname),
                service_category=scat,
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


def _make_charge_record(
    rng: random.Random,
    res: _AzureResourceDef,
    day: date,
    billing_period_start: datetime,
    billing_period_end: datetime,
) -> FocusRecord:
    charge_start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=UTC)
    charge_end = charge_start + timedelta(hours=24)

    variation = Decimal(str(round(rng.uniform(
        _cfg.azure_generator.cost_variation_low,
        _cfg.azure_generator.cost_variation_high,
    ), 6)))
    effective_cost = (res.base_daily_cost * variation).quantize(Decimal("0.000001"))
    list_cost = (effective_cost * Decimal(str(_cfg.azure_generator.list_price_markup))).quantize(
        Decimal("0.000001")
    )
    usage_qty = Decimal("24.000000") if res.usage_unit == "Hrs" else Decimal("1.000000")

    return FocusRecord(
        BillingAccountId=_cfg.azure_generator.billing_account_id,
        SubAccountId=_cfg.azure_generator.sub_account_id,
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
        ProviderName="Microsoft Azure",
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


class AzureCostGenerator:
    """가상 Azure 빌링 생성기.

    Seeded random으로 동일 입력 → 동일 출력을 보장한다.
    CostSource Protocol을 준수한다.
    """

    name: str = "azure"
    resource_id_strategy: str = "terraform_address"

    def __init__(self, seed: int | None = None) -> None:
        self._seed = seed if seed is not None else _cfg.azure_generator.seed

    def generate(self, period_start: date, period_end: date) -> Iterator[FocusRecord]:
        """period_start ~ period_end(미포함) 기간의 Azure FOCUS 레코드를 yield."""
        rng = random.Random(self._seed)

        extra_count = rng.randint(
            _cfg.azure_generator.extra_resources_min,
            _cfg.azure_generator.extra_resources_max,
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
