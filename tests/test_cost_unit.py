"""CostUnit 차원 단위 테스트."""

import dataclasses

import pytest

from dagster_project.core.cost_unit import CostUnit


class TestFromTags:
    def test_all_tags_present(self) -> None:
        cu = CostUnit.from_tags({"team": "platform", "product": "checkout", "env": "prod"})
        assert cu.team == "platform"
        assert cu.product == "checkout"
        assert cu.env == "prod"

    def test_missing_team(self) -> None:
        cu = CostUnit.from_tags({"product": "checkout", "env": "prod"})
        assert cu.team == "unknown"
        assert cu.product == "checkout"

    def test_missing_product(self) -> None:
        cu = CostUnit.from_tags({"team": "data", "env": "staging"})
        assert cu.product == "unknown"

    def test_missing_env(self) -> None:
        cu = CostUnit.from_tags({"team": "ml", "product": "recommender"})
        assert cu.env == "unknown"

    def test_empty_dict(self) -> None:
        cu = CostUnit.from_tags({})
        assert cu.team == "unknown"
        assert cu.product == "unknown"
        assert cu.env == "unknown"

    def test_extra_tags_ignored(self) -> None:
        cu = CostUnit.from_tags(
            {"team": "frontend", "product": "search", "env": "dev", "owner": "alice"}
        )
        assert cu.team == "frontend"
        assert cu.key == "frontend:search:dev"


class TestKey:
    def test_key_format(self) -> None:
        cu = CostUnit(team="data", product="pipeline", env="prod")
        assert cu.key == "data:pipeline:prod"

    def test_unknown_key(self) -> None:
        cu = CostUnit.from_tags({})
        assert cu.key == "unknown:unknown:unknown"


class TestImmutability:
    def test_frozen(self) -> None:
        cu = CostUnit(team="ml", product="recommender", env="staging")
        with pytest.raises(dataclasses.FrozenInstanceError):
            cu.team = "other"  # type: ignore[misc]

    def test_hashable(self) -> None:
        cu1 = CostUnit(team="ml", product="recommender", env="prod")
        cu2 = CostUnit(team="ml", product="recommender", env="prod")
        assert cu1 == cu2
        assert hash(cu1) == hash(cu2)
        assert len({cu1, cu2}) == 1

    def test_different_units_not_equal(self) -> None:
        cu1 = CostUnit(team="ml", product="recommender", env="prod")
        cu2 = CostUnit(team="ml", product="recommender", env="staging")
        assert cu1 != cu2
