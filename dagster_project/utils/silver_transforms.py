"""Silver 레이어 공통 변환 함수 — AWS / GCP 공유."""

from __future__ import annotations

import json

import polars as pl


def flatten_tags(df: pl.DataFrame) -> pl.DataFrame:
    """Tags JSON 컬럼 → team, product, env, cost_unit_key 컬럼 추가."""

    def _extract(tags_json: str | None, key: str) -> str:
        if tags_json is None:
            return "unknown"
        try:
            return str(json.loads(tags_json).get(key, "unknown"))
        except (json.JSONDecodeError, AttributeError):
            return "unknown"

    tags_list = df["Tags"].to_list()
    teams = [_extract(t, "team") for t in tags_list]
    products = [_extract(t, "product") for t in tags_list]
    envs = [_extract(t, "env") for t in tags_list]
    keys = [f"{t}:{p}:{e}" for t, p, e in zip(teams, products, envs, strict=True)]

    return df.with_columns([
        pl.Series("team", teams),
        pl.Series("product", products),
        pl.Series("env", envs),
        pl.Series("cost_unit_key", keys),
        pl.col("ChargePeriodStart").alias("ChargePeriodStartUtc"),
    ])
