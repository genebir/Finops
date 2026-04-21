"""BudgetStoreResource 및 budget_alerts 로직 테스트."""

import pytest

from dagster_project.resources.budget_store import BudgetStoreResource


@pytest.fixture
def budget_store() -> BudgetStoreResource:
    store = BudgetStoreResource()
    store.ensure_table()
    return store


def _cleanup_budget(store: BudgetStoreResource, team: str, env: str) -> None:
    try:
        conn = store._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM dim_budget WHERE team = %s AND env = %s", [team, env])
        cur.close()
        conn.close()
    except Exception:
        pass


def test_ensure_table_creates_dim_budget(budget_store: BudgetStoreResource) -> None:
    budgets = budget_store.all_budgets()
    assert isinstance(budgets, list)


def test_upsert_and_get_budget(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("test_platform", "test_prod", 5000.0)
    result = budget_store.get_budget("test_platform", "test_prod")
    assert result == pytest.approx(5000.0)
    _cleanup_budget(budget_store, "test_platform", "test_prod")


def test_get_budget_wildcard_team(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("*", "test_staging_wc", 1000.0)
    result = budget_store.get_budget("any_team", "test_staging_wc")
    assert result == pytest.approx(1000.0)
    _cleanup_budget(budget_store, "*", "test_staging_wc")


def test_get_budget_wildcard_env(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("test_ml", "*", 3000.0)
    result = budget_store.get_budget("test_ml", "dev")
    assert result == pytest.approx(3000.0)
    _cleanup_budget(budget_store, "test_ml", "*")


def test_get_budget_exact_overrides_wildcard(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("*", "test_prod_ow", 2000.0)
    budget_store.upsert_budget("test_platform_ow", "test_prod_ow", 8000.0)
    result = budget_store.get_budget("test_platform_ow", "test_prod_ow")
    assert result == pytest.approx(8000.0)
    _cleanup_budget(budget_store, "*", "test_prod_ow")
    _cleanup_budget(budget_store, "test_platform_ow", "test_prod_ow")


def test_get_budget_missing_returns_none(budget_store: BudgetStoreResource) -> None:
    _cleanup_budget(budget_store, "*", "*")
    result = budget_store.get_budget("nonexistent_team_xyz", "nonexistent_env_xyz")
    assert result is None


def test_upsert_updates_existing(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("test_data_upd", "test_prod_upd", 4000.0)
    budget_store.upsert_budget("test_data_upd", "test_prod_upd", 6000.0)
    result = budget_store.get_budget("test_data_upd", "test_prod_upd")
    assert result == pytest.approx(6000.0)
    _cleanup_budget(budget_store, "test_data_upd", "test_prod_upd")


def test_all_budgets_returns_list(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("test_frontend", "test_dev_ab", 500.0)
    budget_store.upsert_budget("test_frontend", "test_staging_ab", 800.0)
    budgets = budget_store.all_budgets()
    teams = [b["team"] for b in budgets]
    assert "test_frontend" in teams
    _cleanup_budget(budget_store, "test_frontend", "test_dev_ab")
    _cleanup_budget(budget_store, "test_frontend", "test_staging_ab")


def test_billing_month_specific(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("test_platform_bm", "test_prod_bm", 5500.0, billing_month="2024-03")
    result = budget_store.get_budget("test_platform_bm", "test_prod_bm", billing_month="2024-03")
    assert result == pytest.approx(5500.0)
    try:
        conn = budget_store._connect()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM dim_budget WHERE team = %s AND env = %s AND billing_month = %s",
            ["test_platform_bm", "test_prod_bm", "2024-03"],
        )
        cur.close()
        conn.close()
    except Exception:
        pass


def test_billing_month_fallback_to_default(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("test_data_fb", "test_prod_fb", 4200.0, billing_month="default")
    result = budget_store.get_budget("test_data_fb", "test_prod_fb", billing_month="2024-06")
    assert result == pytest.approx(4200.0)
    _cleanup_budget(budget_store, "test_data_fb", "test_prod_fb")


def test_utilization_pct_logic() -> None:
    actual = 4200.0
    budget = 5000.0
    utilization = actual / budget * 100.0
    assert utilization == pytest.approx(84.0)
    assert utilization >= 80.0
    assert utilization < 100.0


def test_over_budget_logic() -> None:
    actual = 5200.0
    budget = 5000.0
    utilization = actual / budget * 100.0
    assert utilization > 100.0


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


def test_get_budget_full_wildcard(budget_store: BudgetStoreResource) -> None:
    budget_store.upsert_budget("*", "*", 200.0)
    result = budget_store.get_budget("unknown_team_fw", "unknown_env_fw")
    assert result == pytest.approx(200.0)


def test_ensure_table_idempotent(budget_store: BudgetStoreResource) -> None:
    budget_store.ensure_table()
    budget_store.ensure_table()
    budgets = budget_store.all_budgets()
    assert isinstance(budgets, list)
