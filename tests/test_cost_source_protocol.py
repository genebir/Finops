"""CostSource Protocol 및 생성기 구현 검증 테스트."""

from datetime import date


def test_aws_generator_implements_cost_source() -> None:
    """AwsCurGenerator는 CostSource Protocol을 구현한다."""
    from dagster_project.generators.aws_cur_generator import AwsCurGenerator
    gen = AwsCurGenerator(seed=42)
    assert gen.name == "aws"
    assert gen.resource_id_strategy == "terraform_address"
    records = list(gen.generate(date(2024, 1, 1), date(2024, 1, 2)))
    assert len(records) > 0


def test_gcp_generator_implements_cost_source() -> None:
    """GcpBillingGenerator는 CostSource Protocol을 구현한다."""
    from dagster_project.generators.gcp_billing_generator import GcpBillingGenerator
    gen = GcpBillingGenerator(seed=84)
    assert gen.name == "gcp"
    assert gen.resource_id_strategy == "terraform_address"
    records = list(gen.generate(date(2024, 1, 1), date(2024, 1, 2)))
    assert len(records) > 0


def test_azure_generator_implements_cost_source() -> None:
    """AzureCostGenerator는 CostSource Protocol을 구현한다."""
    from dagster_project.generators.azure_cost_generator import AzureCostGenerator
    gen = AzureCostGenerator(seed=126)
    assert gen.name == "azure"
    assert gen.resource_id_strategy == "terraform_address"
    records = list(gen.generate(date(2024, 1, 1), date(2024, 1, 2)))
    assert len(records) > 0


def test_all_generators_produce_focus_records() -> None:
    """모든 생성기는 동일한 FOCUS 1.0 필드를 가진 FocusRecord를 반환한다."""
    from dagster_project.generators.aws_cur_generator import AwsCurGenerator
    from dagster_project.generators.azure_cost_generator import AzureCostGenerator
    from dagster_project.generators.gcp_billing_generator import GcpBillingGenerator

    generators = [
        AwsCurGenerator(seed=42),
        GcpBillingGenerator(seed=84),
        AzureCostGenerator(seed=126),
    ]
    for gen in generators:
        records = list(gen.generate(date(2024, 1, 1), date(2024, 1, 2)))
        assert len(records) > 0
        rec = records[0]
        assert rec.BillingCurrency == "USD"
        assert rec.EffectiveCost >= 0
        assert rec.ProviderName is not None
        assert len(rec.ProviderName) > 0


def test_cost_source_runtime_protocol_check() -> None:
    """CostSource Protocol의 구조를 확인한다."""
    from dagster_project.core.cost_source import CostSource
    from dagster_project.generators.azure_cost_generator import AzureCostGenerator

    gen = AzureCostGenerator(seed=126)
    assert hasattr(gen, "name")
    assert hasattr(gen, "resource_id_strategy")
    assert hasattr(gen, "generate")
    assert callable(gen.generate)
