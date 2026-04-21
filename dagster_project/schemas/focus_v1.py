"""FOCUS 1.0 스키마 — Phase 1 구현 범위."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

import pyarrow as pa
from pydantic import BaseModel, field_validator, model_validator


class ChargeCategory(StrEnum):
    Usage = "Usage"
    Purchase = "Purchase"
    Tax = "Tax"
    Credit = "Credit"
    Adjustment = "Adjustment"


class ServiceCategory(StrEnum):
    AIAndMachineLearning = "AI and Machine Learning"
    Analytics = "Analytics"
    BusinessApplications = "Business Applications"
    Compute = "Compute"
    Database = "Database"
    DeveloperTools = "Developer Tools"
    Identity = "Identity"
    Integration = "Integration"
    Management = "Management"
    Networking = "Networking"
    Security = "Security"
    Storage = "Storage"
    Other = "Other"


class FocusRecord(BaseModel):
    """FOCUS 1.0 비용 레코드 (Phase 1 구현 범위)."""

    model_config = {"arbitrary_types_allowed": True}

    # Identifiers
    BillingAccountId: str
    SubAccountId: str | None = None
    ResourceId: str
    ResourceName: str
    ResourceType: str

    # Time (UTC)
    ChargePeriodStart: datetime
    ChargePeriodEnd: datetime
    BillingPeriodStart: datetime
    BillingPeriodEnd: datetime

    # Cost (Decimal(18,6) — float 절대 금지)
    BilledCost: Decimal
    EffectiveCost: Decimal
    ListCost: Decimal
    ContractedCost: Decimal

    # Currency
    BillingCurrency: str = "USD"

    # Service
    ServiceName: str
    ServiceCategory: ServiceCategory
    ProviderName: str = "AWS"

    # Location
    RegionId: str
    RegionName: str
    AvailabilityZone: str | None = None

    # Charge
    ChargeCategory: ChargeCategory
    ChargeDescription: str | None = None

    # Usage
    UsageQuantity: Decimal | None = None
    UsageUnit: str | None = None
    PricingQuantity: Decimal | None = None
    PricingUnit: str | None = None

    # SKU
    SkuId: str | None = None
    SkuPriceId: str | None = None

    # Commitment (Phase 1 대부분 NULL)
    CommitmentDiscountCategory: str | None = None
    CommitmentDiscountId: str | None = None
    CommitmentDiscountType: str | None = None

    # Tags (JSON 문자열 또는 dict)
    Tags: dict[str, str] | None = None

    @field_validator("Tags", mode="before")
    @classmethod
    def parse_tags(cls, v: Any) -> dict[str, str] | None:
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            parsed = json.loads(v)
            if not isinstance(parsed, dict):
                raise ValueError("Tags JSON must be an object")
            return {str(k): str(val) for k, val in parsed.items()}
        raise ValueError(f"Tags must be a JSON string or dict, got {type(v)}")

    @field_validator("BillingCurrency")
    @classmethod
    def currency_must_be_usd(cls, v: str) -> str:
        if v != "USD":
            raise ValueError(f"Phase 1 only supports USD, got {v!r}")
        return v

    @field_validator("BilledCost", "EffectiveCost", "ListCost", "ContractedCost", mode="before")
    @classmethod
    def coerce_decimal(cls, v: Any) -> Decimal:
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("UsageQuantity", "PricingQuantity", mode="before")
    @classmethod
    def coerce_decimal_optional(cls, v: Any) -> Decimal | None:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @model_validator(mode="after")
    def validate_periods(self) -> FocusRecord:
        if self.ChargePeriodEnd <= self.ChargePeriodStart:
            raise ValueError(
                f"ChargePeriodEnd ({self.ChargePeriodEnd}) must be after "
                f"ChargePeriodStart ({self.ChargePeriodStart})"
            )
        if self.BillingPeriodEnd <= self.BillingPeriodStart:
            raise ValueError(
                f"BillingPeriodEnd ({self.BillingPeriodEnd}) must be after "
                f"BillingPeriodStart ({self.BillingPeriodStart})"
            )
        return self

    @model_validator(mode="after")
    def validate_cost_relationship(self) -> FocusRecord:
        if self.EffectiveCost > self.ListCost:
            raise ValueError(
                f"EffectiveCost ({self.EffectiveCost}) must be <= ListCost ({self.ListCost})"
            )
        return self

    def to_pyarrow_row(self) -> dict[str, Any]:
        """PyIceberg 쓰기용 dict 반환. Decimal → float 변환하지 않고 str 유지."""
        return {
            "BillingAccountId": self.BillingAccountId,
            "SubAccountId": self.SubAccountId,
            "ResourceId": self.ResourceId,
            "ResourceName": self.ResourceName,
            "ResourceType": self.ResourceType,
            "ChargePeriodStart": self.ChargePeriodStart,
            "ChargePeriodEnd": self.ChargePeriodEnd,
            "BillingPeriodStart": self.BillingPeriodStart,
            "BillingPeriodEnd": self.BillingPeriodEnd,
            "BilledCost": str(self.BilledCost),
            "EffectiveCost": str(self.EffectiveCost),
            "ListCost": str(self.ListCost),
            "ContractedCost": str(self.ContractedCost),
            "BillingCurrency": self.BillingCurrency,
            "ServiceName": self.ServiceName,
            "ServiceCategory": self.ServiceCategory.value,
            "ProviderName": self.ProviderName,
            "RegionId": self.RegionId,
            "RegionName": self.RegionName,
            "AvailabilityZone": self.AvailabilityZone,
            "ChargeCategory": self.ChargeCategory.value,
            "ChargeDescription": self.ChargeDescription,
            "UsageQuantity": str(self.UsageQuantity) if self.UsageQuantity is not None else None,
            "UsageUnit": self.UsageUnit,
            "PricingQuantity": (
                str(self.PricingQuantity) if self.PricingQuantity is not None else None
            ),
            "PricingUnit": self.PricingUnit,
            "SkuId": self.SkuId,
            "SkuPriceId": self.SkuPriceId,
            "CommitmentDiscountCategory": self.CommitmentDiscountCategory,
            "CommitmentDiscountId": self.CommitmentDiscountId,
            "CommitmentDiscountType": self.CommitmentDiscountType,
            "Tags": json.dumps(self.Tags) if self.Tags is not None else None,
        }


# PyArrow 스키마 — PyIceberg 테이블 생성 및 직렬화에 사용
FOCUS_PYARROW_SCHEMA = pa.schema(
    [
        pa.field("BillingAccountId", pa.string(), nullable=False),
        pa.field("SubAccountId", pa.string(), nullable=True),
        pa.field("ResourceId", pa.string(), nullable=False),
        pa.field("ResourceName", pa.string(), nullable=False),
        pa.field("ResourceType", pa.string(), nullable=False),
        pa.field("ChargePeriodStart", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("ChargePeriodEnd", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("BillingPeriodStart", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("BillingPeriodEnd", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("BilledCost", pa.string(), nullable=False),
        pa.field("EffectiveCost", pa.string(), nullable=False),
        pa.field("ListCost", pa.string(), nullable=False),
        pa.field("ContractedCost", pa.string(), nullable=False),
        pa.field("BillingCurrency", pa.string(), nullable=False),
        pa.field("ServiceName", pa.string(), nullable=False),
        pa.field("ServiceCategory", pa.string(), nullable=False),
        pa.field("ProviderName", pa.string(), nullable=False),
        pa.field("RegionId", pa.string(), nullable=False),
        pa.field("RegionName", pa.string(), nullable=False),
        pa.field("AvailabilityZone", pa.string(), nullable=True),
        pa.field("ChargeCategory", pa.string(), nullable=False),
        pa.field("ChargeDescription", pa.string(), nullable=True),
        pa.field("UsageQuantity", pa.string(), nullable=True),
        pa.field("UsageUnit", pa.string(), nullable=True),
        pa.field("PricingQuantity", pa.string(), nullable=True),
        pa.field("PricingUnit", pa.string(), nullable=True),
        pa.field("SkuId", pa.string(), nullable=True),
        pa.field("SkuPriceId", pa.string(), nullable=True),
        pa.field("CommitmentDiscountCategory", pa.string(), nullable=True),
        pa.field("CommitmentDiscountId", pa.string(), nullable=True),
        pa.field("CommitmentDiscountType", pa.string(), nullable=True),
        pa.field("Tags", pa.string(), nullable=True),
    ]
)
