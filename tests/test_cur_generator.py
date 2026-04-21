"""AwsCurGenerator 단위 테스트."""

import hashlib
import json
from datetime import date
from decimal import Decimal

import pytest

from dagster_project.generators.aws_cur_generator import _TERRAFORM_RESOURCES, AwsCurGenerator
from dagster_project.schemas.focus_v1 import FocusRecord


def _records_hash(records: list[FocusRecord]) -> str:
    payload = json.dumps(
        [r.to_pyarrow_row() for r in records],
        sort_keys=True,
        default=str,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture
def jan_2024() -> tuple[date, date]:
    return date(2024, 1, 1), date(2024, 2, 1)


class TestDeterminism:
    def test_same_seed_same_output(self, jan_2024: tuple[date, date]) -> None:
        start, end = jan_2024
        gen_a = AwsCurGenerator(seed=42)
        gen_b = AwsCurGenerator(seed=42)
        records_a = list(gen_a.generate(start, end))
        records_b = list(gen_b.generate(start, end))
        assert _records_hash(records_a) == _records_hash(records_b)

    def test_different_seed_different_output(self, jan_2024: tuple[date, date]) -> None:
        start, end = jan_2024
        gen_a = AwsCurGenerator(seed=42)
        gen_b = AwsCurGenerator(seed=99)
        records_a = list(gen_a.generate(start, end))
        records_b = list(gen_b.generate(start, end))
        assert _records_hash(records_a) != _records_hash(records_b)

    def test_different_period_different_output(self) -> None:
        gen = AwsCurGenerator(seed=42)
        rec_jan = list(gen.generate(date(2024, 1, 1), date(2024, 2, 1)))
        rec_feb = list(gen.generate(date(2024, 2, 1), date(2024, 3, 1)))
        assert _records_hash(rec_jan) != _records_hash(rec_feb)


class TestRecordCount:
    def test_daily_records_per_resource(self, jan_2024: tuple[date, date]) -> None:
        start, end = jan_2024
        gen = AwsCurGenerator(seed=42)
        records = list(gen.generate(start, end))
        days = (end - start).days  # 31
        resource_ids = {r.ResourceId for r in records}
        assert len(records) == days * len(resource_ids)

    def test_minimum_resource_count(self, jan_2024: tuple[date, date]) -> None:
        start, end = jan_2024
        gen = AwsCurGenerator(seed=42)
        records = list(gen.generate(start, end))
        resource_ids = {r.ResourceId for r in records}
        # 10개 고정(terraform) + 최소 5개 추가
        assert len(resource_ids) >= 15

    def test_terraform_resources_all_present(self, jan_2024: tuple[date, date]) -> None:
        start, end = jan_2024
        gen = AwsCurGenerator(seed=42)
        records = list(gen.generate(start, end))
        resource_ids = {r.ResourceId for r in records}
        for res in _TERRAFORM_RESOURCES:
            assert res.resource_id in resource_ids


class TestFocusCompliance:
    def test_all_records_valid_pydantic(self, jan_2024: tuple[date, date]) -> None:
        start, end = jan_2024
        gen = AwsCurGenerator(seed=42)
        for record in gen.generate(start, end):
            assert isinstance(record, FocusRecord)
            assert record.BillingCurrency == "USD"
            assert record.ProviderName == "AWS"

    def test_effective_cost_lte_list_cost(self, jan_2024: tuple[date, date]) -> None:
        start, end = jan_2024
        gen = AwsCurGenerator(seed=42)
        for record in gen.generate(start, end):
            assert record.EffectiveCost <= record.ListCost

    def test_charge_period_end_after_start(self, jan_2024: tuple[date, date]) -> None:
        start, end = jan_2024
        gen = AwsCurGenerator(seed=42)
        for record in gen.generate(start, end):
            assert record.ChargePeriodEnd > record.ChargePeriodStart

    def test_all_records_have_team_product_env_tags(self, jan_2024: tuple[date, date]) -> None:
        start, end = jan_2024
        gen = AwsCurGenerator(seed=42)
        for record in gen.generate(start, end):
            assert record.Tags is not None
            assert "team" in record.Tags
            assert "product" in record.Tags
            assert "env" in record.Tags

    def test_costs_are_decimal(self, jan_2024: tuple[date, date]) -> None:
        start, end = jan_2024
        gen = AwsCurGenerator(seed=42)
        for record in list(gen.generate(start, end))[:50]:
            assert isinstance(record.BilledCost, Decimal)
            assert isinstance(record.EffectiveCost, Decimal)


class TestAnomalies:
    def test_anomaly_resources_exist(self, jan_2024: tuple[date, date]) -> None:
        import random

        from dagster_project.generators.aws_cur_generator import _build_extra_resources

        rng = random.Random(42)
        count = rng.randint(5, 20)
        extras = _build_extra_resources(rng, count)
        anomalies = [r for r in extras if r.is_anomaly]
        assert 1 <= len(anomalies) <= 2

    def test_anomaly_cost_significantly_higher(self, jan_2024: tuple[date, date]) -> None:
        import random

        from dagster_project.generators.aws_cur_generator import _build_extra_resources

        rng = random.Random(42)
        count = rng.randint(5, 20)
        extras = _build_extra_resources(rng, count)
        normals = [r for r in extras if not r.is_anomaly]
        anomalies = [r for r in extras if r.is_anomaly]

        if normals and anomalies:
            avg_normal = sum(r.base_daily_cost for r in normals) / len(normals)
            for anomaly in anomalies:
                assert anomaly.base_daily_cost >= avg_normal * Decimal("3")


class TestEdgeCases:
    def test_december_billing_period_wraps_to_next_year(self) -> None:
        """12월 생성 시 BillingPeriodEnd가 다음 해 1월이어야 한다."""
        gen = AwsCurGenerator(seed=42)
        records = list(gen.generate(date(2024, 12, 1), date(2025, 1, 1)))
        assert len(records) > 0
        rec = records[0]
        assert rec.BillingPeriodEnd.year == 2025
        assert rec.BillingPeriodEnd.month == 1

    def test_cur_seed_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CUR_SEED 환경변수가 있으면 해당 값이 seed로 사용된다."""
        monkeypatch.setenv("CUR_SEED", "99")
        gen = AwsCurGenerator()
        assert gen._seed == 99  # noqa: SLF001

    def test_cost_unit_property(self) -> None:
        """_ResourceDef.cost_unit은 tags에서 CostUnit을 생성한다."""
        res = _TERRAFORM_RESOURCES[0]
        cost_unit = res.cost_unit
        assert cost_unit.team == res.tags["team"]
        assert cost_unit.env == res.tags["env"]


class TestResourceIdFormat:
    def test_terraform_resource_id_format(self) -> None:
        for res in _TERRAFORM_RESOURCES:
            parts = res.resource_id.split(".")
            assert len(parts) == 2
            assert parts[0].startswith("aws_")
            assert len(parts[1]) > 0

    def test_terraform_ec2_count(self) -> None:
        ec2 = [r for r in _TERRAFORM_RESOURCES if r.resource_type == "aws_instance"]
        assert len(ec2) == 5

    def test_terraform_rds_count(self) -> None:
        rds = [r for r in _TERRAFORM_RESOURCES if r.resource_type == "aws_db_instance"]
        assert len(rds) == 2

    def test_terraform_s3_count(self) -> None:
        s3 = [r for r in _TERRAFORM_RESOURCES if r.resource_type == "aws_s3_bucket"]
        assert len(s3) == 3
