"""Settings response/request models."""

from pydantic import BaseModel, Field


class SettingItem(BaseModel):
    key: str
    value: str
    value_type: str = "str"  # "float" | "int" | "str" | "bool"
    description: str | None = None


class SettingsResponse(BaseModel):
    items: list[SettingItem]


class SettingCreateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=256)
    value_type: str = Field(default="str", pattern=r"^(float|int|str|bool)$")
    description: str | None = Field(default=None, max_length=256)


class SettingUpdateRequest(BaseModel):
    value: str = Field(min_length=1, max_length=256)
