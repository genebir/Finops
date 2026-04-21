"""GcpBillingGenerator 테스트."""

from datetime import date
from decimal import Decimal

import pytest

from dagster_project.generators.gcp_billing_generator import GcpBillingGenerator
from dagster_project.schemas.focus_v1 import FocusRecord


@pytest.fixture
def generator() -> GcpBillingGenerator:
    return GcpBillingGenerator(seed=999)


def test_deterministic_output(generator: GcpBillingGenerator) -> None:
    """동일 seed → 동일 출력."""
    gen2 = GcpBillingGenerator(seed=999)
    period = (date(2024, 1, 1), date(2024, 1, 3))
    r1 = list(generator.generate(*period))
    r2 = list(gen2.generate(*period))
    assert len(r1) == len(r2)
    assert all(a.ResourceId == b.ResourceId for a, b in zip(r1, r2))
    assert all(a.EffectiveCost == b.EffectiveCost for a, b in zip(r1, r2))


def test_provider_name(generator: GcpBillingGenerator) -> None:
    records = list(generator.generate(date(2024, 1, 1), date(2024, 1, 2)))
    assert all(r.ProviderName == "Google Cloud" for r in records)


def test_resource_ids_are_gcp_format(generator: GcpBillingGenerator) -> None:
    records = list(generator.generate(date(2024, 1, 1), date(2024, 1, 2)))
    for r in records:
        assert "." in r.ResourceId
        # 고정 리소스는 google_ prefix
        fixed_ids = {r.ResourceId for r in records if not r.ResourceId.endswith("_extra_" + r.ResourceId.split("_")[-1])}
        if r.ResourceId in fixed_ids:
            assert r.ResourceId.startswith("google_")


def test_all_records_are_focus_records(generator: GcpBillingGenerator) -> None:
    records = list(generator.generate(date(2024, 1, 1), date(2024, 1, 5)))
    assert all(isinstance(r, FocusRecord) for r in records)


def test_costs_are_decimal(generator: GcpBillingGenerator) -> None:
    records = list(generator.generate(date(2024, 1, 1), date(2024, 1, 2)))
    for r in records:
        assert isinstance(r.EffectiveCost, Decimal)
        assert r.EffectiveCost > Decimal("0")


def test_tags_contain_required_keys(generator: GcpBillingGenerator) -> None:
    records = list(generator.generate(date(2024, 1, 1), date(2024, 1, 2)))
    for r in records:
        assert isinstance(r.Tags, dict)
        assert "team" in r.Tags
        assert "product" in r.Tags
        assert "env" in r.Tags


def test_billing_currency_is_usd(generator: GcpBillingGenerator) -> None:
    records = list(generator.generate(date(2024, 1, 1), date(2024, 1, 2)))
    assert all(r.BillingCurrency == "USD" for r in records)


def test_different_seed_produces_different_output() -> None:
    r1 = list(GcpBillingGenerator(seed=1).generate(date(2024, 1, 1), date(2024, 1, 2)))
    r2 = list(GcpBillingGenerator(seed=2).generate(date(2024, 1, 1), date(2024, 1, 2)))
    costs1 = [r.EffectiveCost for r in r1]
    costs2 = [r.EffectiveCost for r in r2]
    assert costs1 != costs2


def test_gcp_and_aws_use_different_billing_accounts() -> None:
    from dagster_project.generators.aws_cur_generator import AwsCurGenerator
    from dagster_project.config import load_config
    cfg = load_config()

    aws_records = list(AwsCurGenerator().generate(date(2024, 1, 1), date(2024, 1, 2)))
    gcp_records = list(GcpBillingGenerator().generate(date(2024, 1, 1), date(2024, 1, 2)))

    aws_accounts = {r.BillingAccountId for r in aws_records}
    gcp_accounts = {r.BillingAccountId for r in gcp_records}
    assert aws_accounts.isdisjoint(gcp_accounts)


def test_december_billing_period_wraps() -> None:
    """12월 생성 시 BillingPeriodEnd가 다음 해 1월."""
    gen = GcpBillingGenerator(seed=84)
    records = list(gen.generate(date(2024, 12, 1), date(2025, 1, 1)))
    assert len(records) > 0
    assert records[0].BillingPeriodEnd.year == 2025


def test_gcp_cost_unit_property() -> None:
    """_GcpResourceDef.cost_unit은 tags에서 CostUnit을 생성한다."""
    from dagster_project.generators.gcp_billing_generator import _FIXED_RESOURCES
    res = _FIXED_RESOURCES[0]
    cost_unit = res.cost_unit
    assert cost_unit.team == res.tags["team"]
    assert cost_unit.env == res.tags["env"]
