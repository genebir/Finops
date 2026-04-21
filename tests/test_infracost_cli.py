"""InfracostCliResource 단위 테스트 — subprocess mocking 기반."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dagster_project.resources.infracost_cli import InfracostCliResource


def test_breakdown_json_raises_if_path_not_found(tmp_path: Path) -> None:
    """terraform_path가 없으면 FileNotFoundError를 발생시킨다."""
    resource = InfracostCliResource(
        terraform_path=str(tmp_path / "nonexistent"),
        infracost_binary="infracost",
    )
    with pytest.raises(FileNotFoundError, match="Terraform path not found"):
        resource.breakdown_json()


def test_breakdown_json_raises_on_nonzero_returncode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """infracost가 returncode != 0 이면 RuntimeError를 발생시킨다."""
    import subprocess

    tf_dir = tmp_path / "terraform"
    tf_dir.mkdir()

    class _FakeResult:
        returncode = 1
        stderr = "error: infracost failed"
        stdout = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult())

    resource = InfracostCliResource(
        terraform_path=str(tf_dir),
        infracost_binary="infracost",
    )
    with pytest.raises(RuntimeError, match="infracost exited with code 1"):
        resource.breakdown_json()


def test_breakdown_json_returns_parsed_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """infracost 성공 시 JSON 파싱 결과를 반환한다."""
    import subprocess

    tf_dir = tmp_path / "terraform"
    tf_dir.mkdir()

    fake_output = {"projects": [], "totalMonthlyCost": "0.00"}

    class _FakeResult:
        returncode = 0
        stderr = ""
        stdout = json.dumps(fake_output)

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult())

    resource = InfracostCliResource(
        terraform_path=str(tf_dir),
        infracost_binary="infracost",
    )
    result = resource.breakdown_json()
    assert result == fake_output
    assert result["totalMonthlyCost"] == "0.00"
