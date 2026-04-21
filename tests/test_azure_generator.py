"""AzureCostGenerator 테스트 — 결정론적 출력, 스키마, 리소스 형식 검증."""

from datetime import date
from decimal import Decimal

import pytest

from dagster_project.generators.azure_cost_generator import AzureCostGenerator
from dagster_project.schemas.focus_v1 import FocusRecord


@pytest.fixture(scope="module")
def generated_records() -> list[FocusRecord]:
    gen = AzureCostGenerator(seed=126)
    return list(gen.generate(date(2024, 1, 1), date(2024, 2, 1)))


def test_deterministic_output() -> None:
    gen1 = AzureCostGenerator(seed=126)
    gen2 = AzureCostGenerator(seed=126)
    recs1 = list(gen1.generate(date(2024, 1, 1), date(2024, 2, 1)))
    recs2 = list(gen2.generate(date(2024, 1, 1), date(2024, 2, 1)))
    assert len(recs1) == len(recs2)
    assert recs1[0].ResourceId == recs2[0].ResourceId
    assert recs1[0].EffectiveCost == recs2[0].EffectiveCost


def test_different_seed_different_output() -> None:
    gen_az = AzureCostGenerator(seed=126)
    gen_other = AzureCostGenerator(seed=42)
    recs_az = list(gen_az.generate(date(2024, 1, 1), date(2024, 2, 1)))
    recs_other = list(gen_other.generate(date(2024, 1, 1), date(2024, 2, 1)))
    assert recs_az[0].BillingAccountId != recs_other[0].BillingAccountId or \
           recs_az[0].EffectiveCost != recs_other[0].EffectiveCost


def test_provider_name(generated_records: list[FocusRecord]) -> None:
    for rec in generated_records:
        assert rec.ProviderName == "Microsoft Azure"


def test_billing_currency_usd(generated_records: list[FocusRecord]) -> None:
    for rec in generated_records:
        assert rec.BillingCurrency == "USD"


def test_billing_account_id(generated_records: list[FocusRecord]) -> None:
    for rec in generated_records:
        assert rec.BillingAccountId == "AZURE-BILLING-001"


def test_resource_id_format(generated_records: list[FocusRecord]) -> None:
    """ResourceId는 azurerm_<type>.<name> 형식이어야 한다."""
    fixed_prefixes = {
        "azurerm_virtual_machine",
        "azurerm_sql_database",
        "azurerm_storage_account",
        "azurerm_kubernetes_cluster",
        "azurerm_redis_cache",
        "azurerm_cosmosdb_account",
        "azurerm_function_app",
    }
    for rec in generated_records:
        prefix = rec.ResourceId.split(".")[0]
        assert prefix.startswith("azurerm_"), f"ResourceId prefix wrong: {rec.ResourceId}"


def test_cost_positive(generated_records: list[FocusRecord]) -> None:
    for rec in generated_records:
        assert rec.EffectiveCost >= Decimal("0")
        assert rec.ListCost >= rec.EffectiveCost


def test_tags_present(generated_records: list[FocusRecord]) -> None:
    for rec in generated_records:
        tags = rec.Tags if isinstance(rec.Tags, dict) else {}
        assert "team" in tags
        assert "product" in tags
        assert "env" in tags


def test_region_ids(generated_records: list[FocusRecord]) -> None:
    valid_regions = {"eastus", "westus2", "northeurope", "southeastasia"}
    for rec in generated_records:
        assert rec.RegionId in valid_regions


def test_covers_multiple_days(generated_records: list[FocusRecord]) -> None:
    dates = {rec.ChargePeriodStart.date() for rec in generated_records}
    assert len(dates) == 31  # January 2024


def test_fixed_resources_included(generated_records: list[FocusRecord]) -> None:
    resource_ids = {rec.ResourceId for rec in generated_records}
    assert "azurerm_virtual_machine.web_1" in resource_ids
    assert "azurerm_sql_database.main_1" in resource_ids
    assert "azurerm_kubernetes_cluster.ml_cluster_1" in resource_ids


def test_record_count_reasonable(generated_records: list[FocusRecord]) -> None:
    # 31일 × (8 고정 + extra) 리소스, extra는 3~15
    assert len(generated_records) >= 31 * 8
    assert len(generated_records) <= 31 * 25


def test_generate_december_billing_period() -> None:
    """12월 생성 시 billing_period_end가 다음 해 1월이어야 한다."""
    gen = AzureCostGenerator(seed=126)
    records = list(gen.generate(date(2024, 12, 1), date(2025, 1, 1)))
    assert len(records) > 0
    rec = records[0]
    assert rec.BillingPeriodEnd.year == 2025
    assert rec.BillingPeriodEnd.month == 1


def test_cost_unit_property() -> None:
    """_AzureResourceDef.cost_unit 프로퍼티는 tags에서 CostUnit을 생성한다."""
    from dagster_project.generators.azure_cost_generator import _FIXED_RESOURCES
    res = _FIXED_RESOURCES[0]
    cost_unit = res.cost_unit
    assert cost_unit.team == res.tags["team"]
    assert cost_unit.env == res.tags["env"]
