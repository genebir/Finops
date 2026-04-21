"""FocusRecord 스키마 유효성 검증 테스트."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from dagster_project.schemas.focus_v1 import (
    FOCUS_PYARROW_SCHEMA,
    ChargeCategory,
    FocusRecord,
    ServiceCategory,
)


def make_base(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "BillingAccountId": "123456789012",
        "ResourceId": "aws_instance.web_1",
        "ResourceName": "web_1",
        "ResourceType": "aws_instance",
        "ChargePeriodStart": datetime(2024, 1, 1, tzinfo=UTC),
        "ChargePeriodEnd": datetime(2024, 1, 2, tzinfo=UTC),
        "BillingPeriodStart": datetime(2024, 1, 1, tzinfo=UTC),
        "BillingPeriodEnd": datetime(2024, 2, 1, tzinfo=UTC),
        "BilledCost": Decimal("10.0"),
        "EffectiveCost": Decimal("9.0"),
        "ListCost": Decimal("12.0"),
        "ContractedCost": Decimal("10.0"),
        "BillingCurrency": "USD",
        "ServiceName": "Amazon EC2",
        "ServiceCategory": ServiceCategory.Compute,
        "ProviderName": "AWS",
        "RegionId": "us-east-1",
        "RegionName": "US East (N. Virginia)",
        "ChargeCategory": ChargeCategory.Usage,
        "Tags": {"team": "platform", "product": "checkout", "env": "prod"},
    }
    base.update(overrides)
    return base


class TestValidRecord:
    def test_basic_valid(self, valid_record: FocusRecord) -> None:
        assert valid_record.BillingCurrency == "USD"
        assert valid_record.ProviderName == "AWS"

    def test_decimal_coercion_from_float(self) -> None:
        r = FocusRecord(**make_base(BilledCost=10.5, EffectiveCost=9.0, ListCost=12.0, ContractedCost=10.5))  # type: ignore[arg-type]
        assert isinstance(r.BilledCost, Decimal)

    def test_tags_as_json_string(self) -> None:
        tags_str = json.dumps({"team": "data", "product": "search", "env": "prod"})
        r = FocusRecord(**make_base(Tags=tags_str))  # type: ignore[arg-type]
        assert r.Tags == {"team": "data", "product": "search", "env": "prod"}

    def test_tags_as_dict(self) -> None:
        r = FocusRecord(**make_base(Tags={"team": "ml", "product": "recommender", "env": "dev"}))
        assert r.Tags is not None
        assert r.Tags["team"] == "ml"

    def test_optional_fields_none(self) -> None:
        r = FocusRecord(**make_base(Tags=None, AvailabilityZone=None, SkuId=None))
        assert r.Tags is None
        assert r.AvailabilityZone is None


class TestInvalidCurrency:
    def test_non_usd_rejected(self) -> None:
        with pytest.raises(ValidationError, match="USD"):
            FocusRecord(**make_base(BillingCurrency="EUR"))  # type: ignore[arg-type]


class TestPeriodValidation:
    def test_charge_period_end_before_start(self) -> None:
        with pytest.raises(ValidationError, match="ChargePeriodEnd"):
            FocusRecord(
                **make_base(
                    ChargePeriodStart=datetime(2024, 1, 2, tzinfo=UTC),
                    ChargePeriodEnd=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )

    def test_charge_period_equal_rejected(self) -> None:
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        with pytest.raises(ValidationError, match="ChargePeriodEnd"):
            FocusRecord(**make_base(ChargePeriodStart=ts, ChargePeriodEnd=ts))

    def test_billing_period_end_before_start(self) -> None:
        with pytest.raises(ValidationError, match="BillingPeriodEnd"):
            FocusRecord(
                **make_base(
                    BillingPeriodStart=datetime(2024, 2, 1, tzinfo=UTC),
                    BillingPeriodEnd=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )


class TestCostValidation:
    def test_effective_cost_exceeds_list_cost(self) -> None:
        with pytest.raises(ValidationError, match="EffectiveCost"):
            FocusRecord(**make_base(EffectiveCost=Decimal("15.0"), ListCost=Decimal("12.0")))

    def test_effective_cost_equals_list_cost_ok(self) -> None:
        r = FocusRecord(**make_base(EffectiveCost=Decimal("12.0"), ListCost=Decimal("12.0")))
        assert r.EffectiveCost == r.ListCost


class TestToPyarrowRow:
    def test_returns_dict(self, valid_record: FocusRecord) -> None:
        row = valid_record.to_pyarrow_row()
        assert isinstance(row, dict)
        assert "BilledCost" in row

    def test_cost_serialized_as_string(self, valid_record: FocusRecord) -> None:
        row = valid_record.to_pyarrow_row()
        assert isinstance(row["BilledCost"], str)
        assert Decimal(row["BilledCost"]) == valid_record.BilledCost

    def test_tags_serialized_as_json(self, valid_record: FocusRecord) -> None:
        row = valid_record.to_pyarrow_row()
        assert row["Tags"] is not None
        parsed = json.loads(row["Tags"])  # type: ignore[arg-type]
        assert parsed["team"] == "platform"

    def test_schema_field_count(self) -> None:
        assert len(FOCUS_PYARROW_SCHEMA) == 32
