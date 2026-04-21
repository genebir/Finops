"""GET/PUT /api/cloud-config — cloud provider connection settings."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..deps import db_read, db_write

router = APIRouter(prefix="/api/cloud-config", tags=["cloud-config"])

_CLOUD_KEYS = [
    "cloud.aws.enabled", "cloud.aws.region", "cloud.aws.cur_s3_bucket",
    "cloud.aws.cur_s3_prefix", "cloud.aws.account_id",
    "cloud.gcp.enabled", "cloud.gcp.project_id",
    "cloud.gcp.billing_dataset", "cloud.gcp.billing_table",
    "cloud.azure.enabled", "cloud.azure.subscription_id",
    "cloud.azure.tenant_id", "cloud.azure.storage_account",
    "cloud.azure.storage_container",
]

_PROVIDER_GROUPS = {
    "aws":   [k for k in _CLOUD_KEYS if k.startswith("cloud.aws.")],
    "gcp":   [k for k in _CLOUD_KEYS if k.startswith("cloud.gcp.")],
    "azure": [k for k in _CLOUD_KEYS if k.startswith("cloud.azure.")],
}

_DDL = """
CREATE TABLE IF NOT EXISTS platform_settings (
    key         VARCHAR PRIMARY KEY,
    value       VARCHAR NOT NULL,
    value_type  VARCHAR NOT NULL,
    description VARCHAR,
    updated_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
)
"""

_DEFAULTS: dict[str, tuple[str, str, str]] = {
    "cloud.aws.enabled":             ("false",      "bool",  "AWS 클라우드 연동 활성화"),
    "cloud.aws.region":              ("us-east-1",  "str",   "AWS 기본 리전"),
    "cloud.aws.cur_s3_bucket":       ("",           "str",   "AWS CUR S3 버킷명"),
    "cloud.aws.cur_s3_prefix":       ("cur/",       "str",   "AWS CUR S3 경로 접두사"),
    "cloud.aws.account_id":          ("",           "str",   "AWS 계정 ID"),
    "cloud.gcp.enabled":             ("false",      "bool",  "GCP 클라우드 연동 활성화"),
    "cloud.gcp.project_id":          ("",           "str",   "GCP 프로젝트 ID"),
    "cloud.gcp.billing_dataset":     ("",           "str",   "GCP 빌링 BigQuery 데이터셋"),
    "cloud.gcp.billing_table":       ("",           "str",   "GCP 빌링 BigQuery 테이블"),
    "cloud.azure.enabled":           ("false",      "bool",  "Azure 클라우드 연동 활성화"),
    "cloud.azure.subscription_id":   ("",           "str",   "Azure 구독 ID"),
    "cloud.azure.tenant_id":         ("",           "str",   "Azure 테넌트 ID"),
    "cloud.azure.storage_account":   ("",           "str",   "Azure Cost Export 스토리지 계정"),
    "cloud.azure.storage_container": ("",           "str",   "Azure Cost Export 컨테이너명"),
}


def _ensure_cloud_keys(cur: Any) -> None:
    cur.execute(_DDL)
    for key, (value, vtype, desc) in _DEFAULTS.items():
        cur.execute(
            """
            INSERT INTO platform_settings (key, value, value_type, description)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (key) DO NOTHING
            """,
            (key, value, vtype, desc),
        )


def _fetch_provider(cur: Any, provider: str) -> dict[str, Any]:
    keys = _PROVIDER_GROUPS[provider]
    cur.execute(
        "SELECT key, value, value_type, description FROM platform_settings WHERE key = ANY(%s)",
        (keys,),
    )
    rows = {r[0]: {"value": r[1], "value_type": r[2], "description": r[3]} for r in cur.fetchall()}
    # fill missing defaults
    for k in keys:
        if k not in rows:
            val, vtype, desc = _DEFAULTS.get(k, ("", "str", ""))
            rows[k] = {"value": val, "value_type": vtype, "description": desc}
    return rows


@router.get("")
def get_cloud_config() -> dict[str, Any]:
    """전체 클라우드 연결 설정을 provider별로 반환."""
    with db_read() as conn:
        with conn.cursor() as cur:
            _ensure_cloud_keys(cur)
            result: dict[str, Any] = {}
            for provider in ("aws", "gcp", "azure"):
                rows = _fetch_provider(cur, provider)
                result[provider] = {
                    k.split(f"cloud.{provider}.")[1]: v
                    for k, v in rows.items()
                }
    return result


class CloudConfigUpdate(BaseModel):
    provider: str
    key: str
    value: str


@router.put("")
def update_cloud_config(body: CloudConfigUpdate) -> dict[str, str]:
    """단일 클라우드 설정 값 업데이트."""
    if body.provider not in _PROVIDER_GROUPS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider}")

    full_key = f"cloud.{body.provider}.{body.key}"
    if full_key not in _CLOUD_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown key: {full_key}")

    with db_write() as conn:
        with conn.cursor() as cur:
            _ensure_cloud_keys(cur)
            cur.execute(
                "UPDATE platform_settings SET value = %s, updated_at = NOW() WHERE key = %s",
                (body.value, full_key),
            )
            if cur.rowcount == 0:
                val, vtype, desc = _DEFAULTS.get(full_key, ("", "str", ""))
                cur.execute(
                    "INSERT INTO platform_settings (key, value, value_type, description) VALUES (%s, %s, %s, %s)",
                    (full_key, body.value, vtype, desc),
                )
    return {"key": full_key, "value": body.value}


@router.get("/status")
def cloud_connection_status() -> dict[str, Any]:
    """각 provider의 활성화 상태와 설정 완료 여부 반환."""
    with db_read() as conn:
        with conn.cursor() as cur:
            _ensure_cloud_keys(cur)
            cur.execute(
                "SELECT key, value FROM platform_settings WHERE key = ANY(%s)",
                (_CLOUD_KEYS,),
            )
            kv = {r[0]: r[1] for r in cur.fetchall()}

    status: dict[str, Any] = {}
    for provider in ("aws", "gcp", "azure"):
        enabled = kv.get(f"cloud.{provider}.enabled", "false").lower() == "true"
        required_keys = [k for k in _PROVIDER_GROUPS[provider] if not k.endswith(".enabled")]
        configured = all(kv.get(k, "") != "" for k in required_keys)
        status[provider] = {
            "enabled": enabled,
            "configured": configured,
            "missing_keys": [
                k.split(f"cloud.{provider}.")[1]
                for k in required_keys
                if kv.get(k, "") == ""
            ],
        }
    return {"providers": status}
