"""Settings response/request models."""

from pydantic import BaseModel, Field


class SettingItem(BaseModel):
    key: str
    value: str
    value_type: str = "str"  # "float" | "int" | "str" | "bool"
    description: str | None = None


class SettingsResponse(BaseModel):
    items: list[SettingItem]


class SettingUpdateRequest(BaseModel):
    value: str = Field(min_length=1, max_length=256)
