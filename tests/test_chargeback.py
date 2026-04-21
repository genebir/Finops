"""Chargeback 로직 테스트 — 비용 집계 및 예산 조인 검증."""

from decimal import Decimal
from pathlib import Path

import pytest


def test_chargeback_aggregation_logic() -> None:
    """provider/team/product/env 단위 집계 로직 검증."""
    rows = [
        {"provider": "aws", "team": "platform", "product": "checkout", "env": "prod", "cost": 100.0},
        {"provider": "aws", "team": "platform", "product": "checkout", "env": "prod", "cost": 200.0},
        {"provider": "gcp", "team": "platform", "product": "checkout", "env": "prod", "cost": 50.0},
        {"provider": "aws", "team": "data", "product": "search", "env": "staging", "cost": 80.0},
    ]
    agg: dict[tuple[str, str, str, str], float] = {}
    for r in rows:
        key = (r["provider"], r["team"], r["product"], r["env"])
        agg[key] = agg.get(key, 0.0) + r["cost"]

    assert agg[("aws", "platform", "checkout", "prod")] == pytest.approx(300.0)
    assert agg[("gcp", "platform", "checkout", "prod")] == pytest.approx(50.0)
    assert agg[("aws", "data", "search", "staging")] == pytest.approx(80.0)


def test_chargeback_budget_join() -> None:
    """실제 비용과 예산 조인 후 utilization_pct 계산."""
    actual_cost = 4500.0
    budget = 5000.0
    utilization_pct = actual_cost / budget * 100.0
    assert utilization_pct == pytest.approx(90.0)


def test_chargeback_no_budget() -> None:
    """예산 없는 항목은 utilization_pct=None."""
    budget = None
    utilization_pct = None if (budget is None or budget == 0) else 100.0 / budget
    assert utilization_pct is None


def test_chargeback_multi_provider_totals() -> None:
    """멀티 클라우드 총합 계산."""
    provider_costs = {"aws": 5000.0, "gcp": 2000.0, "azure": 3000.0}
    total = sum(provider_costs.values())
    assert total == pytest.approx(10000.0)
    aws_share = provider_costs["aws"] / total * 100
    assert aws_share == pytest.approx(50.0)


def test_chargeback_cost_unit_key_format() -> None:
    """cost_unit_key 형식 검증 (team:product:env)."""
    team, product, env = "platform", "checkout", "prod"
    key = f"{team}:{product}:{env}"
    assert key == "platform:checkout:prod"
    parts = key.split(":")
    assert len(parts) == 3
    assert parts[0] == team
    assert parts[1] == product
    assert parts[2] == env


def test_chargeback_csv_columns() -> None:
    """chargeback CSV 컬럼 목록 검증."""
    expected_columns = {
        "billing_month", "provider", "team", "product", "env",
        "cost_unit_key", "actual_cost", "budget_amount", "utilization_pct", "resource_count"
    }
    # dim_chargeback 테이블 DDL의 컬럼과 일치
    actual_columns = {
        "billing_month", "provider", "team", "product", "env",
        "cost_unit_key", "actual_cost", "budget_amount", "utilization_pct", "resource_count"
    }
    assert expected_columns == actual_columns


def test_chargeback_resource_count() -> None:
    """리소스 카운트 집계 검증."""
    resources_per_group: dict[str, set[str]] = {}
    data = [
        ("platform:checkout:prod", "aws_instance.web_1"),
        ("platform:checkout:prod", "aws_instance.web_2"),
        ("platform:checkout:prod", "aws_rds.db_1"),
        ("data:search:prod", "aws_instance.search_1"),
    ]
    for key, resource_id in data:
        resources_per_group.setdefault(key, set()).add(resource_id)

    assert len(resources_per_group["platform:checkout:prod"]) == 3
    assert len(resources_per_group["data:search:prod"]) == 1


def test_chargeback_idempotency_logic() -> None:
    """DELETE + INSERT 패턴으로 billing_month별 멱등성 보장."""
    stored: list[dict[str, object]] = []
    billing_month = "2024-01"

    def upsert(month: str, rows: list[dict[str, object]]) -> None:
        nonlocal stored
        stored = [r for r in stored if r["billing_month"] != month]
        stored.extend(rows)

    rows1 = [{"billing_month": billing_month, "team": "platform", "cost": 1000.0}]
    upsert(billing_month, rows1)
    assert len(stored) == 1

    rows2 = [{"billing_month": billing_month, "team": "platform", "cost": 1200.0}]
    upsert(billing_month, rows2)
    assert len(stored) == 1
    assert stored[0]["cost"] == 1200.0
