"""Dagster definitions 로딩 테스트."""

from __future__ import annotations

from dagster import Definitions


def test_definitions_loads() -> None:
    """definitions.py 임포트 및 Definitions 객체 생성 검증."""
    from dagster_project.definitions import defs

    assert isinstance(defs, Definitions)


def test_definitions_has_assets() -> None:
    """모든 파이프라인 asset이 등록되어 있는지 확인."""
    from dagster_project.definitions import defs

    asset_graph = defs.resolve_asset_graph()
    asset_keys = {str(k) for k in asset_graph.get_all_asset_keys()}
    # 핵심 asset 존재 확인
    assert any("raw_cur" in k for k in asset_keys)
    assert any("gold_marts" in k for k in asset_keys)
    assert any("fx_rates" in k for k in asset_keys)
