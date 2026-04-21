"""CostUnit 차원 — 팀·제품·환경 기준 비용 집계 단위."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostUnit:
    """모든 비용 데이터를 팀(team)·제품(product)·환경(env) 축으로 환원하는 불변 값 객체."""

    team: str
    product: str
    env: str  # prod | staging | dev

    @classmethod
    def from_tags(cls, tags: dict[str, str]) -> CostUnit:
        return cls(
            team=tags.get("team", "unknown"),
            product=tags.get("product", "unknown"),
            env=tags.get("env", "unknown"),
        )

    @property
    def key(self) -> str:
        return f"{self.team}:{self.product}:{self.env}"
