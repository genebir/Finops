"""Pydantic models for /api/pipeline/* endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class AssetInfo(BaseModel):
    key: str
    group: str | None
    description: str | None
    has_partitions: bool


class AssetListResponse(BaseModel):
    assets: list[AssetInfo]
    total: int


class TriggerRequest(BaseModel):
    assets: list[str]
    partition_key: str | None = None


class TriggerResult(BaseModel):
    asset_key: str
    success: bool
    error: str | None = None
    duration_sec: float | None = None


class TriggerResponse(BaseModel):
    results: list[TriggerResult]
    total: int
    succeeded: int
    failed: int


class PipelinePreset(BaseModel):
    name: str
    description: str
    assets: list[str]
