"""Tests for Cloud Config API — /api/cloud-config."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_cloud_config_returns_200(client: TestClient) -> None:
    r = client.get("/api/cloud-config")
    assert r.status_code == 200


def test_cloud_config_has_all_providers(client: TestClient) -> None:
    body = client.get("/api/cloud-config").json()
    assert "aws" in body
    assert "gcp" in body
    assert "azure" in body


def test_cloud_config_aws_fields(client: TestClient) -> None:
    body = client.get("/api/cloud-config").json()
    aws = body["aws"]
    assert "enabled" in aws
    assert "region" in aws
    assert "cur_s3_bucket" in aws
    assert "cur_s3_prefix" in aws
    assert "account_id" in aws


def test_cloud_config_gcp_fields(client: TestClient) -> None:
    body = client.get("/api/cloud-config").json()
    gcp = body["gcp"]
    assert "enabled" in gcp
    assert "project_id" in gcp
    assert "billing_dataset" in gcp
    assert "billing_table" in gcp


def test_cloud_config_azure_fields(client: TestClient) -> None:
    body = client.get("/api/cloud-config").json()
    azure = body["azure"]
    assert "enabled" in azure
    assert "subscription_id" in azure
    assert "tenant_id" in azure
    assert "storage_account" in azure


def test_cloud_config_value_structure(client: TestClient) -> None:
    body = client.get("/api/cloud-config").json()
    for provider in ("aws", "gcp", "azure"):
        for key, field in body[provider].items():
            assert "value" in field
            assert "value_type" in field
            assert "description" in field


def test_cloud_config_update_valid(client: TestClient) -> None:
    r = client.put("/api/cloud-config", json={
        "provider": "aws", "key": "region", "value": "ap-northeast-2"
    })
    assert r.status_code == 200
    body = r.json()
    assert body["key"] == "cloud.aws.region"
    assert body["value"] == "ap-northeast-2"
    # restore
    client.put("/api/cloud-config", json={"provider": "aws", "key": "region", "value": "us-east-1"})


def test_cloud_config_update_invalid_provider(client: TestClient) -> None:
    r = client.put("/api/cloud-config", json={
        "provider": "alibaba", "key": "region", "value": "cn-east-1"
    })
    assert r.status_code == 400


def test_cloud_config_update_invalid_key(client: TestClient) -> None:
    r = client.put("/api/cloud-config", json={
        "provider": "aws", "key": "nonexistent_key", "value": "test"
    })
    assert r.status_code == 400


def test_cloud_config_status_returns_200(client: TestClient) -> None:
    r = client.get("/api/cloud-config/status")
    assert r.status_code == 200


def test_cloud_config_status_shape(client: TestClient) -> None:
    body = client.get("/api/cloud-config/status").json()
    assert "providers" in body
    for provider in ("aws", "gcp", "azure"):
        p = body["providers"][provider]
        assert "enabled" in p
        assert "configured" in p
        assert "missing_keys" in p
        assert isinstance(p["missing_keys"], list)
