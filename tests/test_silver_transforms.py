"""Silver 변환 테스트 — Tags → CostUnit 파생 정확성."""

import json

import polars as pl

from dagster_project.utils.silver_transforms import flatten_tags as _flatten_tags


def _make_df(tags_list: list[dict | None]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "Tags": [json.dumps(t) if t is not None else None for t in tags_list],
            "ChargePeriodStart": ["2024-01-01T00:00:00+00:00"] * len(tags_list),
        }
    ).with_columns(
        pl.col("ChargePeriodStart").str.to_datetime(time_unit="us", time_zone="UTC")
    )


class TestFlattenTags:
    def test_full_tags_extracted(self) -> None:
        df = _make_df([{"team": "platform", "product": "checkout", "env": "prod"}])
        result = _flatten_tags(df)
        assert result["team"][0] == "platform"
        assert result["product"][0] == "checkout"
        assert result["env"][0] == "prod"
        assert result["cost_unit_key"][0] == "platform:checkout:prod"

    def test_missing_team_defaults_unknown(self) -> None:
        df = _make_df([{"product": "search", "env": "staging"}])
        result = _flatten_tags(df)
        assert result["team"][0] == "unknown"
        assert result["cost_unit_key"][0] == "unknown:search:staging"

    def test_missing_product_defaults_unknown(self) -> None:
        df = _make_df([{"team": "ml", "env": "dev"}])
        result = _flatten_tags(df)
        assert result["product"][0] == "unknown"
        assert result["cost_unit_key"][0] == "ml:unknown:dev"

    def test_missing_env_defaults_unknown(self) -> None:
        df = _make_df([{"team": "data", "product": "api"}])
        result = _flatten_tags(df)
        assert result["env"][0] == "unknown"

    def test_null_tags_all_unknown(self) -> None:
        df = _make_df([None])
        result = _flatten_tags(df)
        assert result["team"][0] == "unknown"
        assert result["product"][0] == "unknown"
        assert result["env"][0] == "unknown"
        assert result["cost_unit_key"][0] == "unknown:unknown:unknown"

    def test_multiple_rows(self) -> None:
        df = _make_df(
            [
                {"team": "platform", "product": "checkout", "env": "prod"},
                {"team": "data", "product": "search", "env": "staging"},
                None,
            ]
        )
        result = _flatten_tags(df)
        assert len(result) == 3
        assert result["cost_unit_key"][0] == "platform:checkout:prod"
        assert result["cost_unit_key"][1] == "data:search:staging"
        assert result["cost_unit_key"][2] == "unknown:unknown:unknown"

    def test_charge_period_start_utc_preserved(self) -> None:
        df = _make_df([{"team": "ml", "product": "rec", "env": "prod"}])
        result = _flatten_tags(df)
        assert "ChargePeriodStartUtc" in result.columns
        assert result["ChargePeriodStartUtc"][0] == result["ChargePeriodStart"][0]

    def test_extra_tags_ignored(self) -> None:
        df = _make_df([{"team": "frontend", "product": "api", "env": "dev", "owner": "alice"}])
        result = _flatten_tags(df)
        assert result["team"][0] == "frontend"
        assert "owner" not in result.columns

    def test_invalid_json_defaults_unknown(self) -> None:
        """Tags가 유효하지 않은 JSON이면 모두 unknown."""
        import polars as pl
        df = pl.DataFrame({
            "Tags": ["{invalid_json"],
            "ChargePeriodStart": ["2024-01-01T00:00:00+00:00"],
        }).with_columns(
            pl.col("ChargePeriodStart").str.to_datetime(time_unit="us", time_zone="UTC")
        )
        result = _flatten_tags(df)
        assert result["team"][0] == "unknown"
        assert result["product"][0] == "unknown"
        assert result["env"][0] == "unknown"
