"""pytest 공통 fixture."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from dagster_project.schemas.focus_v1 import ChargeCategory, FocusRecord, ServiceCategory


@pytest.fixture
def valid_record() -> FocusRecord:
    return FocusRecord(
        BillingAccountId="123456789012",
        ResourceId="aws_instance.web_1",
        ResourceName="web_1",
        ResourceType="aws_instance",
        ChargePeriodStart=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        ChargePeriodEnd=datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC),
        BillingPeriodStart=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        BillingPeriodEnd=datetime(2024, 2, 1, 0, 0, 0, tzinfo=UTC),
        BilledCost=Decimal("10.500000"),
        EffectiveCost=Decimal("9.000000"),
        ListCost=Decimal("12.000000"),
        ContractedCost=Decimal("10.500000"),
        BillingCurrency="USD",
        ServiceName="Amazon EC2",
        ServiceCategory=ServiceCategory.Compute,
        ProviderName="AWS",
        RegionId="us-east-1",
        RegionName="US East (N. Virginia)",
        ChargeCategory=ChargeCategory.Usage,
        Tags={"team": "platform", "product": "checkout", "env": "prod"},
    )
