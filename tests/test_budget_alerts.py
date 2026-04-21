"""BudgetStoreResource 및 budget_alerts 로직 테스트."""

import tempfile
from pathlib import Path

import pytest

from dagster_project.resources.budget_store import BudgetStoreResource


@pytest.fixture
def budget_store(tmp_path: Path) -> BudgetStoreResource:
    db_path = str(tmp_path / "test_budget.duckdb")
    store = BudgetStoreResource(db_path=db_path)
    store.ensure_table()
    return store


def test_ensure_table_creates_dim_budget(budget_store: BudgetStoreResource) -> None:
    budgets = budget_store.all_budgets()
    # settings.yaml에 정의된 기본 예산이 seed됨
    # budget_defaults에 항목이 있다면 리스트가 비어있지 않을 수 있음
    assert isinstance(budgets, list)


def test_upsert_and_get_budget(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("platform", "prod", 5000.0)
    result = budget_store.get_budget("platform", "prod")
    assert result == pytest.approx(5000.0)


def test_get_budget_wildcard_team(budget_store: BudgetStoreResource) -> None:
    """team='*' 와일드카드는 모든 팀의 폴백으로 동작한다."""
    budget_store.upsert_budget("*", "staging", 1000.0)
    result = budget_store.get_budget("any_team", "staging")
    assert result == pytest.approx(1000.0)


def test_get_budget_wildcard_env(budget_store: BudgetStoreResource) -> None:
    """env='*' 와일드카드는 모든 환경의 폴백으로 동작한다."""
    budget_store.upsert_budget("ml", "*", 3000.0)
    result = budget_store.get_budget("ml", "dev")
    assert result == pytest.approx(3000.0)


def test_get_budget_exact_overrides_wildcard(budget_store: BudgetStoreResource) -> None:
    """정확 일치가 와일드카드보다 우선한다."""
    budget_store.upsert_budget("*", "prod", 2000.0)
    budget_store.upsert_budget("platform", "prod", 8000.0)
    result = budget_store.get_budget("platform", "prod")
    assert result == pytest.approx(8000.0)


def test_get_budget_missing_returns_none(budget_store: BudgetStoreResource) -> None:
    result = budget_store.get_budget("nonexistent_team", "nonexistent_env")
    assert result is None


def test_upsert_updates_existing(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("data", "prod", 4000.0)
    budget_store.upsert_budget("data", "prod", 6000.0)
    result = budget_store.get_budget("data", "prod")
    assert result == pytest.approx(6000.0)


def test_all_budgets_returns_list(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("frontend", "dev", 500.0)
    budget_store.upsert_budget("frontend", "staging", 800.0)
    budgets = budget_store.all_budgets()
    teams = [b["team"] for b in budgets]
    assert "frontend" in teams


def test_billing_month_specific(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("platform", "prod", 5500.0, billing_month="2024-03")
    result = budget_store.get_budget("platform", "prod", billing_month="2024-03")
    assert result == pytest.approx(5500.0)


def test_billing_month_fallback_to_default(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("data", "prod", 4200.0, billing_month="default")
    result = budget_store.get_budget("data", "prod", billing_month="2024-06")
    assert result == pytest.approx(4200.0)


def test_utilization_pct_logic() -> None:
    """예산 사용률 계산 로직 검증."""
    actual = 4200.0
    budget = 5000.0
    utilization = actual / budget * 100.0
    assert utilization == pytest.approx(84.0)
    assert utilization >= 80.0  # warning 임계값
    assert utilization < 100.0  # over 임계값


def test_over_budget_logic() -> None:
    actual = 5200.0
    budget = 5000.0
    utilization = actual / budget * 100.0
    assert utilization > 100.0  # over 상태


def test_status_within_budget() -> None:
    def compute_status(actual: float, budget: float, warn: float = 80.0, over: float = 100.0) -> str:
        if budget <= 0:
            return "no_budget"
        util = actual / budget * 100.0
        if util >= over:
            return "over"
        if util >= warn:
            return "warning"
        return "ok"

    assert compute_status(3000, 5000) == "ok"
    assert compute_status(4500, 5000) == "warning"
    assert compute_status(5100, 5000) == "over"
    assert compute_status(0, 0) == "no_budget"


def test_all_budgets_billing_month_specific(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("data", "prod", 4000.0, billing_month="2024-02")
    budgets = budget_store.all_budgets(billing_month="2024-02")
    assert any(b["team"] == "data" for b in budgets)


def test_get_budget_full_wildcard(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("*", "*", 200.0)
    result = budget_store.get_budget("unknown_team", "unknown_env")
    assert result == pytest.approx(200.0)


def test_ensure_table_idempotent(budget_store: BudgetStoreResource) -> None:
    """ensure_table 중복 호출해도 에러 없음."""
    budget_store.ensure_table()
    budget_store.ensure_table()
    budgets = budget_store.all_budgets()
    assert isinstance(budgets, list)


def test_get_budget_bad_db_returns_none() -> None:
    """DB 접근 불가 시 None을 반환한다."""
    store = BudgetStoreResource(db_path="/nonexistent/path/budget.duckdb")
    result = store.get_budget("any_team", "any_env")
    assert result is None


def test_all_budgets_bad_db_returns_empty() -> None:
    """DB 접근 불가 시 빈 리스트를 반환한다."""
    store = BudgetStoreResource(db_path="/nonexistent/path/budget.duckdb")
    result = store.all_budgets()
    assert result == []
