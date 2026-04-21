"""Infracost CLI wrapper Dagster 리소스."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from dagster import ConfigurableResource


class InfracostCliResource(ConfigurableResource):
    """infracost CLI를 subprocess로 실행하는 Dagster 리소스."""

    terraform_path: str = "terraform/sample"
    infracost_binary: str = "infracost"
    subprocess_timeout_sec: int = 120

    def breakdown_json(self) -> dict[str, Any]:
        """infracost breakdown --format json 실행 후 파싱된 결과를 반환."""
        tf_path = Path(self.terraform_path).resolve()
        if not tf_path.exists():
            raise FileNotFoundError(f"Terraform path not found: {tf_path}")

        cmd = [
            self.infracost_binary,
            "breakdown",
            "--path", str(tf_path),
            "--format", "json",
            "--no-color",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.subprocess_timeout_sec,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"infracost exited with code {result.returncode}:\n{result.stderr}"
            )
        return json.loads(result.stdout)  # type: ignore[no-any-return]
