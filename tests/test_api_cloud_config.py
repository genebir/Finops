"""Tests for /api/cloud-config endpoints."""
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


def test_cloud_config_shape(client: TestClient) -> None:
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
    assert "account_id" in aws


def test_cloud_config_gcp_fields(client: TestClient) -> None:
    body = client.get("/api/cloud-config").json()
    gcp = body["gcp"]
    assert "enabled" in gcp
    assert "project_id" in gcp
    assert "billing_dataset" in gcp


def test_cloud_config_azure_fields(client: TestClient) -> None:
    body = client.get("/api/cloud-config").json()
    azure = body["azure"]
    assert "enabled" in azure
    assert "subscription_id" in azure
    assert "tenant_id" in azure


def test_cloud_config_field_value_type(client: TestClient) -> None:
    body = client.get("/api/cloud-config").json()
    for provider in ("aws", "gcp", "azure"):
        for _key, meta in body[provider].items():
            assert "value" in meta
            assert "value_type" in meta


def test_cloud_config_status_returns_200(client: TestClient) -> None:
    r = client.get("/api/cloud-config/status")
    assert r.status_code == 200


def test_cloud_config_status_shape(client: TestClient) -> None:
    body = client.get("/api/cloud-config/status").json()
    assert "providers" in body
    providers = body["providers"]
    for p in ("aws", "gcp", "azure"):
        assert p in providers
        assert "enabled" in providers[p]
        assert "configured" in providers[p]
        assert "missing_keys" in providers[p]


def test_cloud_config_update_returns_200(client: TestClient) -> None:
    r = client.put(
        "/api/cloud-config",
        json={"provider": "aws", "key": "region", "value": "us-west-2"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["value"] == "us-west-2"
    # Restore default
    client.put("/api/cloud-config", json={"provider": "aws", "key": "region", "value": "us-east-1"})


def test_cloud_config_update_unknown_provider(client: TestClient) -> None:
    r = client.put(
        "/api/cloud-config",
        json={"provider": "oci", "key": "region", "value": "us-east-1"},
    )
    assert r.status_code == 400


def test_cloud_config_update_unknown_key(client: TestClient) -> None:
    r = client.put(
        "/api/cloud-config",
        json={"provider": "aws", "key": "nonexistent_key", "value": "x"},
    )
    assert r.status_code == 400
