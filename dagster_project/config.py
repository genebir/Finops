"""AppConfig — config/settings.yaml 기반 설정 로더.

로딩 우선순위:
  1. config/settings.yaml  (기본값, 버전 관리)
  2. config/settings.local.yaml  (로컬 재정의, gitignore)
  3. 환경변수  (CUR_SEED, DUCKDB_PATH 등 — 시크릿/CI용)
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class DataConfig(BaseModel):
    warehouse_path: str = "data/warehouse"
    catalog_db_path: str = "data/catalog.db"
    duckdb_path: str = "data/marts.duckdb"
    reports_dir: str = "data/reports"


class PostgresConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    dbname: str = "finops"
    user: str = "finops_app"
    password: str = "finops_secret_2026"

    @property
    def dsn(self) -> str:
        return f"host={self.host} port={self.port} dbname={self.dbname} user={self.user} password={self.password}"


class DagsterConfig(BaseModel):
    partition_start_date: str = "2024-01-01"


class IcebergConfig(BaseModel):
    catalog_name: str = "finops"
    bronze_table: str = "focus.bronze_cur"
    silver_table: str = "focus.silver_focus"


class CurGeneratorConfig(BaseModel):
    seed: int = 42
    billing_account_id: str = "123456789012"
    sub_account_id: str = "987654321098"
    extra_resources_min: int = 5
    extra_resources_max: int = 20
    cost_variation_low: float = 0.85
    cost_variation_high: float = 1.15
    anomaly_multiplier_low: float = 5.0
    anomaly_multiplier_high: float = 8.0
    list_price_markup: float = 1.15


class ProphetConfig(BaseModel):
    forecast_horizon_days: int = 30
    seasonality_mode: str = "multiplicative"
    min_training_days: int = 14
    hours_per_month: int = 720


class InfracostConfig(BaseModel):
    terraform_path: str = "terraform/sample"
    binary: str = "infracost"
    subprocess_timeout_sec: int = 120


class SlackConfig(BaseModel):
    webhook_timeout_sec: int = 10


class GcpGeneratorConfig(BaseModel):
    seed: int = 84
    project_id: str = "my-finops-project"
    billing_account_id: str = "GCP-BILLING-001"
    sub_account_id: str = "GCP-PROJECT-001"
    extra_resources_min: int = 3
    extra_resources_max: int = 15
    cost_variation_low: float = 0.80
    cost_variation_high: float = 1.20
    anomaly_multiplier_low: float = 4.0
    anomaly_multiplier_high: float = 7.0
    list_price_markup: float = 1.10


class GcpIcebergConfig(BaseModel):
    bronze_table: str = "focus.bronze_cur_gcp"
    silver_table: str = "focus.silver_focus_gcp"


class AzureGeneratorConfig(BaseModel):
    seed: int = 126
    billing_account_id: str = "AZURE-BILLING-001"
    sub_account_id: str = "AZURE-SUB-001"
    extra_resources_min: int = 3
    extra_resources_max: int = 15
    cost_variation_low: float = 0.80
    cost_variation_high: float = 1.20
    anomaly_multiplier_low: float = 4.0
    anomaly_multiplier_high: float = 7.0
    list_price_markup: float = 1.12


class AzureIcebergConfig(BaseModel):
    bronze_table: str = "focus.bronze_cur_azure"
    silver_table: str = "focus.silver_focus_azure"


class BudgetEntryConfig(BaseModel):
    team: str
    env: str
    amount: float


class BudgetDefaultsConfig(BaseModel):
    entries: list[BudgetEntryConfig] = Field(default_factory=list)


class OperationalDefaultsConfig(BaseModel):
    """DuckDB platform_settings 테이블의 초기 기본값."""

    anomaly_zscore_warning: float = 2.0
    anomaly_zscore_critical: float = 3.0
    variance_over_pct: float = 20.0
    variance_under_pct: float = -20.0
    alert_critical_pct: float = 50.0
    reporting_lookback_days: int = 30
    reporting_top_resources_limit: int = 20
    reporting_top_cost_units_limit: int = 10


class AppConfig(BaseModel):
    data: DataConfig = Field(default_factory=DataConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    dagster: DagsterConfig = Field(default_factory=DagsterConfig)
    iceberg: IcebergConfig = Field(default_factory=IcebergConfig)
    cur_generator: CurGeneratorConfig = Field(default_factory=CurGeneratorConfig)
    gcp_generator: GcpGeneratorConfig = Field(default_factory=GcpGeneratorConfig)
    gcp_iceberg: GcpIcebergConfig = Field(default_factory=GcpIcebergConfig)
    azure_generator: AzureGeneratorConfig = Field(default_factory=AzureGeneratorConfig)
    azure_iceberg: AzureIcebergConfig = Field(default_factory=AzureIcebergConfig)
    budget_defaults: BudgetDefaultsConfig = Field(default_factory=BudgetDefaultsConfig)
    prophet: ProphetConfig = Field(default_factory=ProphetConfig)
    infracost: InfracostConfig = Field(default_factory=InfracostConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    operational_defaults: OperationalDefaultsConfig = Field(
        default_factory=OperationalDefaultsConfig
    )


def _deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    """중첩 딕셔너리를 재귀적으로 병합한다. override 값이 우선."""
    result: dict[str, object] = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)  # type: ignore[arg-type]
        else:
            result[key] = val
    return result


def _load_yaml(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _apply_env_overrides(cfg: dict[str, object]) -> dict[str, object]:
    """환경변수로 특정 설정을 재정의한다."""
    overrides: list[tuple[list[str], str]] = [
        (["cur_generator", "seed"], "CUR_SEED"),
        (["data", "duckdb_path"], "DUCKDB_PATH"),
        (["data", "warehouse_path"], "ICEBERG_WAREHOUSE"),
        (["data", "reports_dir"], "REPORTS_DIR"),
        (["infracost", "terraform_path"], "TERRAFORM_PATH"),
        (["infracost", "binary"], "INFRACOST_BINARY"),
        (["postgres", "host"], "POSTGRES_HOST"),
        (["postgres", "port"], "POSTGRES_PORT"),
        (["postgres", "dbname"], "POSTGRES_DBNAME"),
        (["postgres", "user"], "POSTGRES_USER"),
        (["postgres", "password"], "POSTGRES_PASSWORD"),
    ]
    result = dict(cfg)
    for keys, env_var in overrides:
        val = os.environ.get(env_var)
        if val is not None:
            node: dict[str, object] = result
            for k in keys[:-1]:
                node = node.setdefault(k, {})  # type: ignore[assignment]
            node[keys[-1]] = int(val) if env_var in ("CUR_SEED", "POSTGRES_PORT") else val
    return result


_CONFIG_DIR = Path(__file__).parent.parent / "config"


@lru_cache(maxsize=1)
def load_config() -> AppConfig:
    """AppConfig를 로드하고 캐싱한다.

    config/settings.yaml → settings.local.yaml → 환경변수 순서로 적용한다.
    """
    base_path = _CONFIG_DIR / "settings.yaml"
    local_path = _CONFIG_DIR / "settings.local.yaml"

    data: dict[str, object] = {}
    if base_path.exists():
        data = _load_yaml(base_path)
    if local_path.exists():
        data = _deep_merge(data, _load_yaml(local_path))
    data = _apply_env_overrides(data)

    return AppConfig.model_validate(data)
