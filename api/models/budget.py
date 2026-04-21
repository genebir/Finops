"""Budget response/request models."""

from pydantic import BaseModel, Field


class BudgetItem(BaseModel):
    """Computed budget status (read-only view from dim_budget_status or derived)."""

    team: str
    env: str
    budget_amount: float
    actual_cost: float
    used_pct: float
    status: str  # "ok" | "warning" | "over" | "unknown"


class BudgetResponse(BaseModel):
    items: list[BudgetItem]
    total_budget: float
    total_actual: float


class BudgetEntry(BaseModel):
    """Raw dim_budget row (editable)."""

    team: str
    env: str
    budget_amount: float
    billing_month: str = "default"


class BudgetEntryListResponse(BaseModel):
    items: list[BudgetEntry]


class BudgetCreateRequest(BaseModel):
    team: str = Field(min_length=1, max_length=64)
    env: str = Field(min_length=1, max_length=32)
    budget_amount: float = Field(ge=0)
    billing_month: str = Field(default="default", max_length=16)


class BudgetUpdateRequest(BaseModel):
    budget_amount: float = Field(ge=0)
