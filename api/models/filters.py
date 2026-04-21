"""Shared filter options used to populate dashboard dropdowns."""

from pydantic import BaseModel


class FiltersResponse(BaseModel):
    teams: list[str]
    envs: list[str]
    providers: list[str]
    services: list[str]
    billing_months: list[str]
    date_min: str | None
    date_max: str | None
