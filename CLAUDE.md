# FinOps Platform — 완전 구현 사양서

> 이 문서는 Claude Code가 본 프로젝트를 **처음부터 동일하게 재현**하는 데 필요한 모든 컨텍스트를 담고 있다.
> Phase 1 → Phase 2 → Phase 3 → Phase 4 순서로 구현하며, 각 Phase는 이전 Phase 위에 증분 확장된다.

---

## 1. 프로젝트 목표

로컬 환경에서 돌아가는 **멀티 클라우드 FinOps 플랫폼**을 만든다. 핵심 질문:

1. **"지금 가장 많은 비용을 발생시키는 게 뭐야?"** — Top-N 비용 드라이버 (서비스·리소스·팀·태그별, AWS+GCP+Azure 통합)
2. **"이상하게 튄 비용이 있어?"** — Z-score + IsolationForest 멀티 탐지기
3. **"예측이랑 실제가 얼마나 달라?"** — Infracost(Terraform 기반) + Prophet(시계열 기반) Variance 분석
4. **"예산 대비 현황은?"** — 팀/환경별 예산 관리, 초과 알림, Chargeback 리포트
5. **"전체 현황을 한눈에 보고 싶다"** — Streamlit 웹 대시보드 (6개 탭)

**확장성 원칙:** `CostSource`, `ForecastProvider`, `AnomalyDetector`, `AlertSink` 등 **Protocol 기반 추상화**로 새 클라우드·탐지기·알림을 코드 수정 없이 추가할 수 있어야 한다.

**하드코딩 금지 원칙:** 모든 설정은 `config/settings.yaml` (정적 설정), DuckDB `platform_settings` 테이블 (런타임 임계값), 또는 환경변수로 관리한다. 소스 코드에 수치·경로를 직접 쓰지 않는다.

---

## 2. 기술 스택

| 레이어 | 도구 | 역할 |
|---|---|---|
| Orchestrator | Dagster (≥1.8) | Asset 기반 파이프라인 관리 |
| 고속 전처리 | Polars (≥1.0) | Bronze→Silver 정제 |
| Table Format | Apache Iceberg (via PyIceberg) | 로컬 레이크하우스 |
| Catalog | SqlCatalog (SQLite) | 로컬 Iceberg 메타스토어 |
| Analytics | DuckDB (≥1.0) | Silver→Gold 집계, 분석 마트 |
| Validation | Pydantic v2 | 스키마·값 검증 |
| Config | PyYAML + Pydantic | 정적 설정 로딩 |
| Cost Forecast | Infracost CLI | Terraform 기반 비용 예측 |
| ML Forecast | Prophet (≥1.1) | 시계열 기반 비용 예측 |
| ML Anomaly | scikit-learn (≥1.4) | IsolationForest 이상치 탐지 |
| Alerting | slack-sdk (≥3.0) | Slack Webhook 알림 |
| CLI Dashboard | Rich (≥13.0) | 터미널 대시보드 |
| Web Dashboard | Streamlit (≥1.35) + Plotly (≥5.0) | 웹 대시보드 |
| Standard | FOCUS 1.0 | 비용 데이터 규격 |
| Language | Python 3.14+ | |
| Package Mgmt | uv | |
| Lint/Type | ruff + mypy (strict) | |

---

## 3. 전체 아키텍처 (Phase 1~4 완성 상태)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  AWS 파이프라인          GCP 파이프라인          Azure 파이프라인               │
│  [raw_cur]               [raw_cur_gcp]            [raw_cur_azure]             │
│  seed=42                 seed=84                  seed=126                    │
│       │                        │                        │                     │
│       ▼ Pydantic 검증           ▼                        ▼                    │
│  [bronze_iceberg]        [bronze_iceberg_gcp]  [bronze_iceberg_azure]         │
│       │                        │                        │                     │
│       ▼ flatten_tags            ▼                        ▼                    │
│  [silver_focus]          [silver_focus_gcp]    [silver_focus_azure]           │
│       │                        │                        │                     │
│       ▼ provider='aws'  provider='gcp'         provider='azure'               │
│  [gold_marts]────────[gold_marts_gcp]─────[gold_marts_azure]                 │
│               ↘              ↓             ↙                                  │
│          fact_daily_cost (provider 컬럼으로 3개 클라우드 통합)                 │
│          dim_cost_unit / v_top_resources_30d / v_top_cost_units_30d           │
│                      │                                                         │
│       ┌──────────────┼──────────────────────────────────┐                    │
│       │              │                    │              │                    │
│       ▼              ▼                    ▼              ▼                    │
│  [terraform]  [anomaly_detection]  [prophet_forecast]  [budget_alerts]       │
│  [infracost]  ZScore + IF 멀티탐지  신뢰구간 예측        팀/환경별 예산 관리    │
│       │             │                    │              │                    │
│       ▼             ▼                    ▼              ▼                    │
│  [variance]  [alert_dispatch]  [forecast_variance_prophet]  [chargeback]     │
│  dim_forecast  anomaly_scores    dim_prophet_forecast        dim_chargeback  │
│       │             │                    │              │                    │
│       └─────────────┴────────────────────┴──────────────┘                   │
│                        ▼                                                       │
│                 data/reports/*.csv                                             │
│                 scripts/dashboard.py (Rich CLI)                                │
│                 scripts/streamlit_app.py (Web Dashboard)                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 완성된 디렉토리 구조

```
finops-platform/
├── CLAUDE.md
├── pyproject.toml
├── README.md
├── .env.example
├── .gitignore
├── config/
│   ├── settings.yaml              # 정적 설정 (버전 관리)
│   └── settings.local.yaml        # 로컬 재정의 (gitignore)
├── dagster_project/
│   ├── __init__.py
│   ├── definitions.py
│   ├── config.py                  # AppConfig (Pydantic + YAML 로더)
│   ├── assets/
│   │   ├── __init__.py
│   │   ├── raw_cur.py             # AWS CUR 생성
│   │   ├── raw_cur_gcp.py         # GCP 빌링 생성
│   │   ├── raw_cur_azure.py       # Azure 빌링 생성  [Phase 4]
│   │   ├── bronze_iceberg.py      # AWS Bronze 적재
│   │   ├── bronze_iceberg_gcp.py  # GCP Bronze 적재
│   │   ├── bronze_iceberg_azure.py # Azure Bronze 적재  [Phase 4]
│   │   ├── silver_focus.py        # AWS Silver 정제
│   │   ├── silver_focus_gcp.py    # GCP Silver 정제
│   │   ├── silver_focus_azure.py  # Azure Silver 정제  [Phase 4]
│   │   ├── gold_marts.py          # AWS Gold 마트
│   │   ├── gold_marts_gcp.py      # GCP Gold 마트
│   │   ├── gold_marts_azure.py    # Azure Gold 마트  [Phase 4]
│   │   ├── infracost_forecast.py  # Infracost 예측
│   │   ├── variance.py            # Infracost vs 실제 편차
│   │   ├── anomaly_detection.py   # 멀티 탐지기 이상치 탐지
│   │   ├── alert_dispatch.py      # 알림 발송
│   │   ├── prophet_forecast.py    # Prophet 시계열 예측
│   │   ├── forecast_variance_prophet.py  # Prophet 예측 정확도
│   │   ├── budget_alerts.py       # 예산 사용률 + 초과 알림  [Phase 4]
│   │   └── chargeback.py          # 팀별 비용 배부 리포트  [Phase 4]
│   ├── core/
│   │   ├── __init__.py
│   │   ├── cost_source.py         # CostSource Protocol
│   │   ├── forecast_provider.py   # ForecastProvider Protocol + ForecastRecord
│   │   ├── anomaly_detector.py    # AnomalyDetector Protocol + AnomalyResult
│   │   ├── alert_sink.py          # AlertSink Protocol + Alert
│   │   └── cost_unit.py           # CostUnit 차원
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── aws_cur_generator.py   # CostSource 구현체 (가상 AWS)
│   │   ├── gcp_billing_generator.py  # CostSource 구현체 (가상 GCP)
│   │   └── azure_cost_generator.py   # CostSource 구현체 (가상 Azure)  [Phase 4]
│   ├── detectors/
│   │   ├── __init__.py
│   │   ├── zscore_detector.py     # Z-score 탐지기
│   │   └── isolation_forest_detector.py  # IsolationForest 탐지기
│   ├── providers/
│   │   ├── __init__.py
│   │   └── prophet_provider.py    # ProphetProvider
│   ├── sinks/
│   │   ├── __init__.py
│   │   ├── console_sink.py        # ConsoleSink
│   │   └── slack_sink.py          # SlackSink
│   ├── resources/
│   │   ├── __init__.py
│   │   ├── iceberg_catalog.py     # IcebergCatalogResource
│   │   ├── duckdb_io.py           # DuckDBResource
│   │   ├── infracost_cli.py       # InfracostCliResource
│   │   ├── settings_store.py      # SettingsStoreResource (platform_settings)
│   │   └── budget_store.py        # BudgetStoreResource (dim_budget)  [Phase 4]
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── focus_v1.py            # Pydantic FocusRecord
│   └── utils/
│       ├── __init__.py
│       └── silver_transforms.py   # flatten_tags (AWS/GCP/Azure 공유)
├── sql/
│   └── marts/
│       ├── fact_daily_cost.sql    # DDL only (CREATE TABLE IF NOT EXISTS)
│       ├── dim_cost_unit.sql      # CREATE OR REPLACE TABLE AS SELECT
│       ├── v_top_resources_30d.sql  # {{lookback_days}}, {{top_resources_limit}} 치환
│       ├── anomaly_scores.sql     # CREATE TABLE IF NOT EXISTS
│       └── v_variance.sql         # {{variance_over_pct}}, {{variance_under_pct}} 치환
├── terraform/
│   └── sample/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── scripts/
│   ├── dashboard.py               # Rich 터미널 대시보드
│   └── run_phase2.py              # Phase 2 수동 실행 헬퍼
├── data/                          # gitignored
│   ├── warehouse/                 # Iceberg 데이터
│   ├── catalog.db                 # SqlCatalog SQLite
│   ├── marts.duckdb               # DuckDB 파일
│   └── reports/                   # 출력 CSV
└── tests/
    ├── conftest.py                # valid_record fixture, clear_config_cache fixture
    ├── test_focus_schema.py
    ├── test_cur_generator.py
    ├── test_gcp_generator.py
    ├── test_idempotency.py
    ├── test_silver_transforms.py
    ├── test_variance.py
    ├── test_anomaly_detection.py
    ├── test_alert_dispatch.py
    ├── test_prophet_forecast.py
    ├── test_settings_store.py
    ├── test_isolation_forest.py
    └── test_forecast_variance_prophet.py
```

---

## 5. FOCUS 1.0 구현 범위

### 구현 컬럼

- **Identifiers**: `BillingAccountId`, `SubAccountId`, `ResourceId`, `ResourceName`, `ResourceType`
- **Time**: `ChargePeriodStart`, `ChargePeriodEnd`, `BillingPeriodStart`, `BillingPeriodEnd` (UTC)
- **Cost**: `BilledCost`, `EffectiveCost`, `ListCost`, `ContractedCost` — **모두 `Decimal(18,6)`**
- **Currency**: `BillingCurrency` (`USD` 고정)
- **Service**: `ServiceName`, `ServiceCategory`, `ProviderName` (`AWS` 또는 `Google Cloud`)
- **Location**: `RegionId`, `RegionName`, `AvailabilityZone` (GCP는 None 허용)
- **Charge**: `ChargeCategory` (Enum: Usage|Purchase|Tax|Credit|Adjustment), `ChargeDescription`
- **Usage**: `UsageQuantity`, `UsageUnit`, `PricingQuantity`, `PricingUnit`
- **SKU**: `SkuId`, `SkuPriceId`
- **Tags**: `Tags` (dict → Pydantic 검증 시 JSON 문자열도 허용, Silver에서 평탄화)

### Tags 정책

모든 리소스(AWS/GCP 모두)에 반드시 `team`, `product`, `env` 태그를 심는다.
이 세 태그가 `cost_unit_key = team:product:env` 차원의 기초가 된다.

---

## 6. 핵심 추상화 (Protocol 기반)

### 6.1 `CostSource`

```python
# core/cost_source.py
class CostSource(Protocol):
    name: str  # "aws" | "gcp"
    resource_id_strategy: str  # "terraform_address"

    def generate(self, period_start: date, period_end: date) -> Iterable[FocusRecord]: ...
```

구현체: `AwsCurGenerator` (seed=42), `GcpBillingGenerator` (seed=84)

### 6.2 `ForecastProvider`

```python
# core/forecast_provider.py
@dataclass
class ForecastRecord:
    resource_address: str
    monthly_cost: Decimal
    hourly_cost: Decimal
    currency: str
    forecast_generated_at: datetime
    lower_bound_monthly_cost: Decimal = Decimal("0")  # Prophet 신뢰구간
    upper_bound_monthly_cost: Decimal = Decimal("0")  # Prophet 신뢰구간

class ForecastProvider(Protocol):
    name: str  # "infracost" | "prophet"
    def forecast(self, scope: ForecastScope) -> list[ForecastRecord]: ...
```

구현체: `InfracostProvider`, `ProphetProvider`

### 6.3 `AnomalyDetector`

```python
# core/anomaly_detector.py
@dataclass
class AnomalyResult:
    resource_id: str
    cost_unit_key: str
    team: str; product: str; env: str
    charge_date: date
    effective_cost: Decimal
    mean_cost: Decimal
    std_cost: Decimal
    z_score: float
    is_anomaly: bool
    severity: str        # "critical" | "warning"
    detector_name: str = "zscore"  # "zscore" | "isolation_forest"

class AnomalyDetector(Protocol):
    name: str
    def detect(self, df: pl.DataFrame) -> list[AnomalyResult]: ...
```

구현체: `ZScoreDetector`, `IsolationForestDetector`

### 6.4 `AlertSink`

```python
# core/alert_sink.py
@dataclass
class Alert:
    alert_type: str   # "anomaly" | "variance_over" | "variance_under"
    severity: str     # "info" | "warning" | "critical"
    resource_id: str
    cost_unit_key: str
    message: str
    actual_cost: Decimal
    reference_cost: Decimal
    deviation_pct: float
    triggered_at: datetime

class AlertSink(Protocol):
    name: str
    def send(self, alert: Alert) -> None: ...
    def send_batch(self, alerts: list[Alert]) -> None: ...
```

구현체: `ConsoleSink` (항상 활성), `SlackSink` (`SLACK_WEBHOOK_URL` 환경변수 설정 시)

### 6.5 `CostUnit` 차원

```python
# core/cost_unit.py
@dataclass(frozen=True)
class CostUnit:
    team: str; product: str; env: str

    @classmethod
    def from_tags(cls, tags: dict[str, str]) -> "CostUnit": ...

    @property
    def key(self) -> str:
        return f"{self.team}:{self.product}:{self.env}"
```

---

## 7. 설정 시스템

### 7.1 계층 구조 (우선순위 낮음 → 높음)

```
config/settings.yaml          ← 기본값, 버전 관리
config/settings.local.yaml    ← 로컬 재정의 (gitignore)
환경변수                       ← CI/CD, 시크릿
DuckDB platform_settings      ← 런타임 임계값 (Dagster 재시작 불필요)
```

### 7.2 `config/settings.yaml` 전체 구조

```yaml
data:
  warehouse_path: "data/warehouse"
  catalog_db_path: "data/catalog.db"
  duckdb_path: "data/marts.duckdb"
  reports_dir: "data/reports"

dagster:
  partition_start_date: "2024-01-01"

iceberg:
  catalog_name: "finops"
  bronze_table: "focus.bronze_cur"
  silver_table: "focus.silver_focus"

cur_generator:
  seed: 42                          # CUR_SEED 환경변수로 재정의 가능
  billing_account_id: "123456789012"
  sub_account_id: "987654321098"
  extra_resources_min: 5
  extra_resources_max: 20
  cost_variation_low: 0.85
  cost_variation_high: 1.15
  anomaly_multiplier_low: 5.0
  anomaly_multiplier_high: 8.0
  list_price_markup: 1.15

gcp_generator:
  seed: 84                          # AWS와 다른 시드
  project_id: "my-finops-project"
  billing_account_id: "GCP-BILLING-001"
  sub_account_id: "GCP-PROJECT-001"
  extra_resources_min: 3
  extra_resources_max: 15
  cost_variation_low: 0.80
  cost_variation_high: 1.20
  anomaly_multiplier_low: 4.0
  anomaly_multiplier_high: 7.0
  list_price_markup: 1.10

gcp_iceberg:
  bronze_table: "focus.bronze_cur_gcp"
  silver_table: "focus.silver_focus_gcp"

prophet:
  forecast_horizon_days: 30
  seasonality_mode: "multiplicative"
  min_training_days: 14
  hours_per_month: 720

infracost:
  terraform_path: "terraform/sample"
  binary: "infracost"
  subprocess_timeout_sec: 120

slack:
  webhook_timeout_sec: 10

# 아래 값은 DuckDB platform_settings 테이블의 초기 seed값으로 사용
operational_defaults:
  anomaly_zscore_warning: 2.0
  anomaly_zscore_critical: 3.0
  variance_over_pct: 20.0
  variance_under_pct: -20.0
  alert_critical_pct: 50.0
  reporting_lookback_days: 30
  reporting_top_resources_limit: 20
  reporting_top_cost_units_limit: 10
```

### 7.3 환경변수 목록

| 환경변수 | 매핑 경로 | 용도 |
|---|---|---|
| `CUR_SEED` | `cur_generator.seed` | AWS CUR 생성 시드 |
| `DUCKDB_PATH` | `data.duckdb_path` | DuckDB 파일 경로 |
| `ICEBERG_WAREHOUSE` | `data.warehouse_path` | Iceberg 웨어하우스 경로 |
| `REPORTS_DIR` | `data.reports_dir` | 리포트 출력 디렉토리 |
| `TERRAFORM_PATH` | `infracost.terraform_path` | Infracost 분석 경로 |
| `INFRACOST_BINARY` | `infracost.binary` | Infracost 바이너리 경로 |
| `SLACK_WEBHOOK_URL` | (직접 읽기) | Slack Webhook URL |

### 7.4 DuckDB `platform_settings` 테이블

`SettingsStoreResource.ensure_table()`이 최초 실행 시 아래 기본값으로 seed한다. 이미 존재하는 키는 덮어쓰지 않는다.

```
anomaly.zscore.warning          = 2.0
anomaly.zscore.critical         = 3.0
variance.threshold.over_pct     = 20.0
variance.threshold.under_pct    = 20.0
alert.critical_deviation_pct    = 50.0
alert.slack_timeout_sec         = 10
reporting.lookback_days         = 30
reporting.top_resources_limit   = 20
reporting.top_cost_units_limit  = 10
infracost.subprocess_timeout_sec = 120
anomaly.active_detectors        = "zscore,isolation_forest"
isolation_forest.contamination  = 0.05
isolation_forest.n_estimators   = 100
isolation_forest.random_state   = 42
isolation_forest.score_critical = -0.20
isolation_forest.score_warning  = -0.05
```

런타임 변경:
```sql
UPDATE platform_settings SET value = '3.0' WHERE key = 'anomaly.zscore.warning';
```

---

## 8. 주요 설계 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| **fact_daily_cost 통합** | `provider` 컬럼으로 AWS+GCP 단일 테이블 | 멀티 클라우드 집계를 단일 쿼리로 처리 |
| **Gold 마트 멱등성** | `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE provider=? AND month=?` + `INSERT` | `CREATE OR REPLACE`는 타 provider 데이터를 삭제함 |
| **anomaly_scores 멱등성** | `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE month=?` + `INSERT` | 동일 방식 |
| **dim_prophet_forecast 멱등성** | `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE resource_id IN (...)` + `INSERT` | Prophet은 모든 히스토리로 학습 후 resource 단위 교체 |
| **dim_cost_unit** | `CREATE OR REPLACE TABLE AS SELECT FROM fact_daily_cost` | 전체 재생성이 안전하고 빠름 |
| **Infracost 조인 키** | CUR ResourceId를 `aws_instance.web_1` 형식으로 심어 자동 매칭 | terraform 리소스 주소와 일치 |
| **IsolationForest 최소 샘플** | 10개 미만 그룹 건너뜀 | 모델 안정성 |
| **Prophet 신뢰구간** | `yhat_lower`/`yhat_upper` 존재 여부 체크 후 사용 | mock 테스트에서 해당 컬럼이 없을 수 있음 |
| **Gold 마트 _INSERT_FACT_SQL** | `gold_marts.py`에 상수로 정의, `gold_marts_gcp.py`에서 import | AWS/GCP가 동일 INSERT 로직 공유 |
| **flatten_tags 공유** | `utils/silver_transforms.py`에 `flatten_tags()` 정의 | AWS/GCP silver asset이 동일 로직 사용 |
| **Bronze/Silver 스키마 공유** | GCP asset이 `bronze_iceberg.py`의 `_ICEBERG_SCHEMA`, `_PARTITION_SPEC` import | 스키마 중복 제거 |
| **load_config lru_cache** | `@lru_cache(maxsize=1)` — 테스트는 `clear_config_cache` fixture로 초기화 | `conftest.py`에 `autouse=False` fixture 제공 |
| **통화** | USD 고정 | FX 변환은 Phase 4 |
| **시간대** | 모든 timestamp UTC | Silver에서 `ChargePeriodStartUtc` 컬럼 유지 |
| **Cost 타입** | `Decimal(18,6)` | float 절대 금지 |

---

## 9. 중요 구현 주의사항 (반드시 지킬 것)

1. **asset 파일에 `from __future__ import annotations` 금지**
   Dagster가 런타임에 타입 힌트를 검사하는데, `from __future__ import annotations`가 있으면 `AssetExecutionContext`를 문자열로 처리해 `DagsterInvalidDefinitionError`가 발생한다.
   → `anomaly_detection.py`, `alert_dispatch.py`, `prophet_forecast.py`, `forecast_variance_prophet.py`, `gold_marts_gcp.py`, `raw_cur_gcp.py` 등 모든 asset 파일에 해당.

2. **DuckDB `ON CONFLICT DO UPDATE SET updated_at = CURRENT_TIMESTAMP` 금지**
   DuckDB는 `CURRENT_TIMESTAMP`를 컬럼명으로 인식하여 Binder Error가 발생한다.
   → `settings_store.py`에서 `SELECT` 후 조건부 `UPDATE`/`INSERT` 패턴 사용.

3. **`platform_settings` ALTER TABLE 마이그레이션**
   `anomaly_scores` 테이블에 `detector_name` 컬럼을 추가할 때:
   ```python
   conn.execute("ALTER TABLE anomaly_scores ADD COLUMN IF NOT EXISTS detector_name VARCHAR DEFAULT 'zscore'")
   ```
   `dim_prophet_forecast`에도 동일하게 신뢰구간 컬럼 마이그레이션 필요.

4. **Silver asset은 Bronze 전체를 읽고 월로 필터링**
   PyIceberg가 `scan().to_polars()`로 파티션 푸시다운을 하지 않으므로 Python 레벨에서 월 필터링 수행:
   ```python
   df = df.filter(pl.col("ChargePeriodStart").dt.to_string("%Y-%m").str.starts_with(month_str))
   ```

5. **Prophet mock 테스트**
   `yhat_lower`/`yhat_upper` 컬럼 없는 mock DataFrame으로 테스트할 때 `ProphetProvider`가 graceful fallback하도록 구현됨:
   ```python
   lower_sum = float(horizon_rows["yhat_lower"].sum()) if "yhat_lower" in horizon_rows.columns else 0.0
   ```

---

## 10. pyproject.toml

```toml
[project]
name = "finops-platform"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
    "dagster>=1.8",
    "dagster-webserver>=1.8",
    "polars>=1.0",
    "duckdb>=1.0",
    "pyiceberg[sql-sqlite,pyarrow]>=0.7",
    "pydantic>=2.0",
    "python-dotenv>=1.0",
    "rich>=13.0",
    "pyarrow>=14.0",
    "prophet>=1.1",
    "slack-sdk>=3.0",
    "pyyaml>=6.0",
    "scikit-learn>=1.4",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.4",
    "mypy>=1.10",
]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "C4", "PTH"]
ignore = ["E501"]

[tool.mypy]
strict = true
python_version = "3.14"
ignore_missing_imports = false
warn_return_any = true
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = ["prophet", "prophet.*", "yaml"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--tb=short"

[tool.dagster]
module_name = "dagster_project.definitions"
```

---

## 11. Phase 1 구현 계획

### Step 1-1: 프로젝트 부트스트랩
- `pyproject.toml` 작성 (Section 10 참고)
- `.gitignore`: `data/`, `.venv/`, `__pycache__/`, `.dagster/`, `config/settings.local.yaml`
- `.env.example`: `SLACK_WEBHOOK_URL=`, `CUR_SEED=`, `DUCKDB_PATH=`

### Step 1-2: FOCUS 1.0 스키마 — `schemas/focus_v1.py`
- `FocusRecord` Pydantic 모델
- `ChargeCategory`, `ServiceCategory` Enum
- Validators: `ChargePeriodEnd > ChargePeriodStart`, `EffectiveCost <= ListCost`, `BillingCurrency == "USD"`, Tags dict/JSON 모두 허용
- `to_pyarrow_row()` 헬퍼, `FOCUS_PYARROW_SCHEMA` PyArrow 스키마 상수

### Step 1-3: Cost Unit 차원 — `core/cost_unit.py`
Section 6.5 코드 그대로 구현

### Step 1-4: CostSource Protocol + AWS 생성기
- `core/cost_source.py`: Protocol
- `generators/aws_cur_generator.py`: `AwsCurGenerator`
  - `_cfg = load_config()` 최상단에 선언, 모든 파라미터를 `_cfg.cur_generator.*`로 참조
  - Seeded `random.Random(self._seed)` — 동일 입력 = 동일 출력
  - 고정 리소스 9개 (`_TERRAFORM_RESOURCES`): aws_instance 5개, aws_db_instance 2개, aws_s3_bucket 3개 — terraform/sample과 ResourceId 일치
  - 추가 랜덤 리소스 (extra_resources_min~max개): 가중치 기반 서비스 선택
  - 추가 리소스 중 2개를 의도적 이상치 (anomaly_multiplier 배율)로 설정

### Step 1-5: Iceberg 카탈로그 리소스 — `resources/iceberg_catalog.py`
- `ConfigurableResource`, `SqlCatalog` 기반
- `ensure_table(name, schema, partition_spec)`, `load_table(name)`
- `ensure_namespace(name)` 내부 호출

### Step 1-6: Raw CUR Asset — `assets/raw_cur.py`
```python
_cfg = load_config()
MONTHLY_PARTITIONS = MonthlyPartitionsDefinition(start_date=_cfg.dagster.partition_start_date)

@asset(partitions_def=MONTHLY_PARTITIONS, ...)
def raw_cur(context: AssetExecutionContext) -> list[FocusRecord]:
    ...
```
- Pydantic re-validation 수행, 오류 시 `ValueError` raise

### Step 1-7: Bronze Iceberg Asset — `assets/bronze_iceberg.py`
- `_TABLE_NAME = "focus.bronze_cur"` (하드코딩 — iceberg.bronze_table과 일치, 스키마 재사용을 위해 모듈 상수로 유지)
- PyArrow Table → Iceberg overwrite
- `_ICEBERG_SCHEMA`, `_PARTITION_SPEC` 모듈 레벨 상수로 선언 (GCP asset에서 import)

### Step 1-8: Silver Asset — `assets/silver_focus.py`
- `flatten_tags(df)` → `utils/silver_transforms.py`에서 import
- Bronze 전체 읽기 → Python 레벨 월 필터링 → `flatten_tags` → Silver overwrite
- `_SILVER_ICEBERG_SCHEMA`, `_SILVER_PARTITION_SPEC` 모듈 레벨 상수 (GCP asset에서 import)

### Step 1-9: Gold 마트 — `sql/marts/*.sql` + `assets/gold_marts.py`

**`sql/marts/fact_daily_cost.sql`** — DDL만 (SELECT 없음):
```sql
CREATE TABLE IF NOT EXISTS fact_daily_cost (
    provider         VARCHAR        NOT NULL DEFAULT 'aws',
    charge_date      DATE           NOT NULL,
    resource_id      VARCHAR        NOT NULL,
    resource_name    VARCHAR,
    resource_type    VARCHAR,
    service_name     VARCHAR,
    service_category VARCHAR,
    region_id        VARCHAR,
    team             VARCHAR        NOT NULL,
    product          VARCHAR        NOT NULL,
    env              VARCHAR        NOT NULL,
    cost_unit_key    VARCHAR        NOT NULL,
    effective_cost   DECIMAL(18, 6) NOT NULL,
    billed_cost      DECIMAL(18, 6) NOT NULL,
    list_cost        DECIMAL(18, 6) NOT NULL,
    record_count     BIGINT         NOT NULL
);
```

**`assets/gold_marts.py`**:
- `_INSERT_FACT_SQL` 상수 정의 (provider, silver_view를 `str.format()`으로 주입)
- `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN IF NOT EXISTS provider` (마이그레이션) + `DELETE WHERE provider='aws' AND month=?` + `INSERT`
- `dim_cost_unit.sql`: `CREATE OR REPLACE TABLE AS SELECT FROM fact_daily_cost`
- `v_top_resources_30d.sql`: `{{lookback_days}}`, `{{top_resources_limit}}` 플레이스홀더를 `.replace()`로 치환
- `v_top_cost_units_30d`: Python f-string으로 인라인 SQL

### Step 1-10: Terraform 샘플 — `terraform/sample/main.tf`
- EC2 5개, RDS 2개, S3 3개
- `aws_instance.web_1`, `aws_instance.web_2`, `aws_instance.api_1`, `aws_instance.api_2`, `aws_instance.ml_1`
- `aws_db_instance.main_1`, `aws_db_instance.analytics_1`
- `aws_s3_bucket.assets_1`, `aws_s3_bucket.assets_2`, `aws_s3_bucket.assets_3`
- 태그: `team`, `product`, `env` — CUR 생성기와 동일

### Step 1-11: Infracost Provider & Asset
- `resources/infracost_cli.py`: `ConfigurableResource`, `subprocess_timeout_sec: int` 필드, `infracost breakdown --path ... --format json` 실행
- `core/forecast_provider.py`: `ForecastScope`, `ForecastRecord` (Section 6.2), `ForecastProvider` Protocol
- `assets/infracost_forecast.py`: JSON 파싱 → `dim_forecast` DuckDB 테이블

### Step 1-12: Variance Asset — `assets/variance.py`
- `v_variance.sql` 읽기 → `{{variance_over_pct}}`, `{{variance_under_pct}}` 치환 (settings_store에서)
- `data/reports/variance_YYYYMM.csv` 출력
- status: `over` / `under` / `ok` / `unmatched`

### Step 1-13: Definitions & 테스트
- `definitions.py`: 모든 asset + resource 등록, `_cfg = load_config()` 후 resource 초기화
- 테스트: `test_focus_schema.py`, `test_cur_generator.py`, `test_idempotency.py`, `test_silver_transforms.py`, `test_variance.py`
- 커버리지 70% 이상

---

## 12. Phase 2 구현 계획

### Step 2-1: 설정 시스템 구축

**`config/settings.yaml`** — Section 7.2 전체 작성

**`dagster_project/config.py`** — `AppConfig` Pydantic 모델:
```python
@lru_cache(maxsize=1)
def load_config() -> AppConfig:
    # settings.yaml → settings.local.yaml → 환경변수 순으로 deep merge
```

**`resources/settings_store.py`** — `SettingsStoreResource`:
- `platform_settings` DuckDB 테이블 관리
- `ensure_table()`: CREATE + seed 기본값 (ON CONFLICT DO NOTHING)
- `get_float()`, `get_int()`, `get_str()`, `set_value()`, `all_settings()`
- **주의**: `ON CONFLICT DO UPDATE SET ... = CURRENT_TIMESTAMP` 사용 금지 → SELECT 후 UPDATE/INSERT

**`tests/conftest.py`** — `clear_config_cache` fixture:
```python
@pytest.fixture
def clear_config_cache():
    load_config.cache_clear()
    yield
    load_config.cache_clear()
```

### Step 2-2: 이상치 탐지 (Z-score)

**`core/anomaly_detector.py`** — `AnomalyResult` dataclass + `AnomalyDetector` Protocol (Section 6.3)

**`detectors/zscore_detector.py`** — `ZScoreDetector`:
- `resource_id + cost_unit_key + team + product + env` 그룹별 전체 기간 mean/std
- `std == 0` → z_score = 0 (이상치 아님)
- warning/critical만 반환 (ok 제외)
- `detector_name="zscore"` 명시

**`sql/marts/anomaly_scores.sql`**:
```sql
CREATE TABLE IF NOT EXISTS anomaly_scores (
    resource_id VARCHAR NOT NULL, cost_unit_key VARCHAR NOT NULL,
    team VARCHAR NOT NULL, product VARCHAR NOT NULL, env VARCHAR NOT NULL,
    charge_date DATE NOT NULL, effective_cost DECIMAL(18,6) NOT NULL,
    mean_cost DECIMAL(18,6) NOT NULL, std_cost DECIMAL(18,6) NOT NULL,
    z_score DOUBLE NOT NULL, is_anomaly BOOLEAN NOT NULL, severity VARCHAR NOT NULL
);
```

**`assets/anomaly_detection.py`** — asset 파일이므로 `from __future__ import annotations` 금지:
- `settings_store.ensure_table()` 후 임계값 읽기
- `DELETE WHERE month=?` + INSERT 패턴
- `ALTER TABLE anomaly_scores ADD COLUMN IF NOT EXISTS detector_name VARCHAR DEFAULT 'zscore'`

### Step 2-3: 알림

**`core/alert_sink.py`** — `Alert` dataclass + `AlertSink` Protocol (Section 6.4)

**`sinks/console_sink.py`** — `ConsoleSink`: Python `logging` 모듈 사용

**`sinks/slack_sink.py`** — `SlackSink`:
- `urllib.request.urlopen` 사용 (slack-sdk 아님)
- `SLACK_WEBHOOK_URL` 환경변수에서 webhook_url 읽기
- timeout은 `load_config().slack.webhook_timeout_sec`

**`assets/alert_dispatch.py`** — asset 파일이므로 `from __future__ import annotations` 금지:
- `anomaly_scores`에서 severity 기준 Alert 생성
- `variance_YYYYMM.csv`에서 over/under Alert 생성
- `ConsoleSink` 항상 + `SlackSink` 환경변수 있을 때만

### Step 2-4: Prophet 예측

**`providers/prophet_provider.py`**:
- `try: from prophet import Prophet / except ImportError: Prophet = None`
- `_MIN_TRAINING_DAYS = load_config().prophet.min_training_days`
- `_cfg = load_config()` — hours_per_month 등 참조
- `forecast_from_df(df)`: resource_id별 Prophet fit → yhat 합산
- `yhat_lower`/`yhat_upper` 컬럼 존재 여부 체크 후 신뢰구간 계산

**`assets/prophet_forecast.py`** — asset 파일이므로 `from __future__ import annotations` 금지:
- `CREATE TABLE IF NOT EXISTS dim_prophet_forecast (...)`
- `ALTER TABLE dim_prophet_forecast ADD COLUMN IF NOT EXISTS lower_bound_monthly_cost ...`
- `ALTER TABLE dim_prophet_forecast ADD COLUMN IF NOT EXISTS upper_bound_monthly_cost ...`
- `DELETE WHERE resource_id IN (SELECT resource_id FROM prophet_rows)` + INSERT

### Step 2-5: 테스트
- `test_anomaly_detection.py`, `test_alert_dispatch.py`, `test_prophet_forecast.py`, `test_settings_store.py`
- Prophet mock: `pd.DataFrame({"yhat": [...]})` (yhat_lower/upper 없어도 graceful fallback)

---

## 13. Phase 3 구현 계획

### Step 3-1: GCP 파이프라인

**`generators/gcp_billing_generator.py`** — `GcpBillingGenerator`:
- `_cfg.gcp_generator.*` 참조
- 고정 리소스 6개: `google_compute_instance`, `google_sql_database_instance`, `google_storage_bucket`, `google_bigquery_dataset`, `google_cloudfunctions_function`
- `ProviderName = "Google Cloud"`, `AvailabilityZone = None`
- ResourceId 형식: `google_compute_instance.web_1`

**`assets/raw_cur_gcp.py`** — `GcpBillingGenerator()` 사용, `MONTHLY_PARTITIONS` 재사용

**`assets/bronze_iceberg_gcp.py`**:
```python
from .bronze_iceberg import _ICEBERG_SCHEMA, _PARTITION_SPEC  # 스키마 재사용
table_name = _cfg.gcp_iceberg.bronze_table
```

**`assets/silver_focus_gcp.py`**:
```python
from .silver_focus import _SILVER_ICEBERG_SCHEMA, _SILVER_PARTITION_SPEC  # 스키마 재사용
from ..utils.silver_transforms import flatten_tags
bronze_table_name = _cfg.gcp_iceberg.bronze_table
silver_table_name = _cfg.gcp_iceberg.silver_table
```

**`assets/gold_marts_gcp.py`**:
```python
from .gold_marts import _INSERT_FACT_SQL, _SQL_DIR  # INSERT 공유
# silver_focus_gcp 읽기 → DELETE WHERE provider='gcp' AND month=? → INSERT provider='gcp'
# dim_cost_unit 재생성 (전체 데이터 기반)
```

**`utils/silver_transforms.py`**:
```python
def flatten_tags(df: pl.DataFrame) -> pl.DataFrame:
    # Tags JSON → team, product, env, cost_unit_key, ChargePeriodStartUtc
```

### Step 3-2: IsolationForest 탐지기

**`detectors/isolation_forest_detector.py`** — `IsolationForestDetector`:
- `_MIN_SAMPLES = 10` — 최소 샘플 미만 그룹 건너뜀
- `try: from sklearn.ensemble import IsolationForest / except ImportError: raise`
- `contamination`, `n_estimators`, `random_state`, `score_critical`, `score_warning` 파라미터
- `df.group_by(group_keys, maintain_order=True)` — Polars 그룹 이터레이션
- `predictions == -1` → 이상치, `score < score_critical` → critical, else → warning
- `detector_name = "isolation_forest"`

### Step 3-3: 멀티 탐지기 anomaly_detection 업데이트

**`assets/anomaly_detection.py`** 업데이트:
- `active_detectors_str = settings_store.get_str("anomaly.active_detectors", "zscore")`
- `"zscore" in active_detectors` → `ZScoreDetector` 실행
- `"isolation_forest" in active_detectors` → `IsolationForestDetector` 실행 (ImportError → warning log + 건너뜀)
- rows dict에 `detector_name` 추가

### Step 3-4: Prophet 신뢰구간 + forecast_variance_prophet

**`core/forecast_provider.py`** — `ForecastRecord`에 필드 추가:
```python
lower_bound_monthly_cost: Decimal = Decimal("0")
upper_bound_monthly_cost: Decimal = Decimal("0")
```

**`providers/prophet_provider.py`** 업데이트:
- `yhat_lower`/`yhat_upper` 컬럼 존재 체크 후 추출
- `hourly_cost = monthly_cost / Decimal(str(_cfg.prophet.hours_per_month))`

**`assets/forecast_variance_prophet.py`** — asset 파일이므로 `from __future__ import annotations` 금지:
- `dim_prophet_forecast` JOIN `fact_daily_cost` (월 집계)
- status: `within_bounds` / `above_upper` / `below_lower` / `no_actual`
- `dim_forecast_variance_prophet` DuckDB 테이블 + CSV 출력
- `DELETE WHERE billing_month=?` + INSERT

### Step 3-5: Rich 대시보드

**`scripts/dashboard.py`**:
```
uv run python scripts/dashboard.py [--month YYYY-MM]
```
- `argparse` — `--month` 기본값: `date.today().strftime("%Y-%m")`
- `_provider_summary()`: AWS/GCP 클라우드별 월간 비용
- `_top_resources()`: Top 10 리소스
- `_anomaly_summary()`: Critical 우선 이상치 목록
- `_prophet_forecast_summary()`: 예측 정확도 (dim_forecast_variance_prophet)

### Step 3-6: definitions.py 업데이트

```python
from .assets import (
    raw_cur, raw_cur_gcp,
    bronze_iceberg, bronze_iceberg_gcp,
    silver_focus, silver_focus_gcp,
    gold_marts, gold_marts_gcp,
    infracost_forecast, variance,
    anomaly_detection, alert_dispatch,
    prophet_forecast, forecast_variance_prophet,
)
```

### Step 3-7: 테스트
- `test_gcp_generator.py`: 결정론적 출력, ProviderName, resource_id 형식, 태그, BillingAccountId 분리
- `test_isolation_forest.py`: spike 탐지, 샘플 부족 건너뜀, detector_name, multi-resource isolation
- `test_forecast_variance_prophet.py`: ForecastRecord 신뢰구간 필드, status 로직, AnomalyResult detector_name

---

## 14. 코딩 컨벤션

- Python 3.14+, **모든 함수에 완전한 타입 힌트**
- `ruff` (line-length=100) + `mypy --strict` 통과 필수
- 금액은 **반드시 `decimal.Decimal`** (float 절대 금지)
- 날짜는 `datetime.date`, 시각은 `datetime.datetime` with `tzinfo=UTC`
- I/O 사이드이펙트 있는 코드는 `@asset`으로만. 순수 함수는 `core/`, `schemas/`, `utils/`에.
- 모든 asset에 docstring + Dagster `description` 필수
- asset 파일에서 로깅은 `context.log.info/warning/error` 사용 (print 금지)
- asset 파일 외에서는 Python `logging` 모듈 사용
- **asset 파일에 `from __future__ import annotations` 절대 금지**
- 소스 코드에 수치·경로 하드코딩 금지 — 항상 `_cfg.*` 또는 `settings_store.get_*()`
- `except Exception:` 지양 — 구체적 예외 타입 사용

---

## 15. 멱등성 체크리스트

- [x] AWS/GCP CUR 생성기 seed 고정 시 동일 출력
- [x] Iceberg Bronze는 파티션 단위 `overwrite` (append 금지)
- [x] `fact_daily_cost`: `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE provider=? AND month=?` + `INSERT`
- [x] `anomaly_scores`: `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE month=?` + `INSERT`
- [x] `dim_prophet_forecast`: `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE resource_id IN (...)` + `INSERT`
- [x] `dim_cost_unit`: `CREATE OR REPLACE TABLE AS SELECT FROM fact_daily_cost` (전체 재생성)
- [x] `v_top_resources_30d`, `v_top_cost_units_30d`, `v_variance`: `CREATE OR REPLACE VIEW`
- [x] 전체 파이프라인 2회 실행 후 동일 결과

---

## 16. 실행 방법

```bash
# 부트스트랩
uv sync
cp .env.example .env

# Infracost CLI 설치 (선택)
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh
infracost configure set api_key <YOUR_KEY>

# Dagster 실행
uv run dagster dev
# → http://localhost:3000 → 전체 assets materialize

# 터미널 대시보드 (Rich CLI)
uv run python scripts/dashboard.py --month 2026-03

# 웹 대시보드 (Streamlit)  [Phase 4]
uv run streamlit run scripts/streamlit_app.py

# Phase 2 수동 테스트 스크립트
uv run python scripts/run_phase2.py 2026-03-01

# 테스트
uv run pytest
uv run pytest --cov=dagster_project --cov-fail-under=70

# 린트 / 타입 체크
uv run ruff check .
uv run mypy dagster_project
```

---

## 17. Phase 4 구현 내용

Phase 4는 Azure 클라우드 지원, 예산 관리, Chargeback, Streamlit 대시보드를 추가했다.

### 신규 파일
- `dagster_project/generators/azure_cost_generator.py` — AzureCostGenerator (seed=126)
  - Services: VM, Blob Storage, Azure SQL, AKS, Redis, Cosmos DB, Functions
  - Regions: eastus, westus2, northeurope, southeastasia
  - ResourceId 포맷: `azurerm_<type>.<name>`
- `dagster_project/assets/raw_cur_azure.py` → `bronze_iceberg_azure.py` → `silver_focus_azure.py` → `gold_marts_azure.py`
- `dagster_project/resources/budget_store.py` — BudgetStoreResource
  - DuckDB `dim_budget` 테이블 관리
  - (team, env) 키 + `*` 와일드카드 지원
  - 우선순위: 정확 일치 > team 특정(env=*) > env 특정(team=*) > 전체 와일드카드
  - settings.yaml `budget_defaults.entries`에서 초기 seed
- `dagster_project/assets/budget_alerts.py` — 예산 사용률 계산 및 초과 알림
  - `dim_budget_status` 테이블 (billing_month, team, env, utilization_pct, status)
  - warning: >= budget.alert_threshold_pct (기본 80%)
  - over: >= budget.over_threshold_pct (기본 100%)
  - ConsoleSink + SlackSink 발송, `data/reports/budget_alerts_YYYYMM.csv`
- `dagster_project/assets/chargeback.py` — 팀별 비용 배부 리포트
  - `dim_chargeback` 테이블 (provider/team/product/env별 집계)
  - dim_budget과 조인하여 utilization_pct 포함
  - `data/reports/chargeback_YYYYMM.csv`
- `scripts/streamlit_app.py` — Streamlit 웹 대시보드
  - 6개 탭: Overview, Cost Explorer, Anomalies, Forecast, Budget, Chargeback
  - `@st.cache_data(ttl=300)` for DuckDB queries
  - Plotly 차트 (bar, area, scatter, pie)
  - 사이드바: 월/클라우드 provider 필터

### 설정 추가 (settings.yaml)
- `azure_generator`: seed=126, billing_account_id="AZURE-BILLING-001" 등
- `azure_iceberg`: bronze_table, silver_table
- `budget_defaults.entries`: (team, env, amount) 목록

### config.py 추가 클래스
- `AzureGeneratorConfig`, `AzureIcebergConfig`
- `BudgetEntryConfig`, `BudgetDefaultsConfig`

### platform_settings 신규 항목
- `budget.alert_threshold_pct = 80.0` — 예산 사용률 경고 임계값
- `budget.over_threshold_pct = 100.0` — 예산 사용률 초과 임계값

### definitions.py 업데이트
- BudgetStoreResource 리소스 등록
- Azure 파이프라인 + budget_alerts + chargeback asset 등록

### 테스트
- `tests/test_azure_generator.py` — 14개 테스트
- `tests/test_budget_alerts.py` — 18개 테스트 (와일드카드 우선순위 포함)
- `tests/test_chargeback.py` — 8개 테스트
- `tests/test_settings_store.py` — 12개 테스트
- `tests/test_infracost_cli.py` — 3개 테스트
- `tests/test_cost_source_protocol.py` — 5개 테스트

**최종 결과:** 200 passed, 70.23% coverage

## 18. Phase 5 미구현 항목 (향후 계획)

- 멀티 클라우드 실제 연동 (AWS CUR S3 Export, GCP Billing Export API, Azure Cost Management API)
- FX 통화 변환 (EUR/KRW 등 실시간 환율)
- IsolationForest 이외 추가 탐지기 (LSTM, ARIMA 기반)
- 이메일 AlertSink (SMTP 기반)
- Prophet 모델 파라미터 자동 튜닝 (Cross-validation)
- 예산 편집 UI (Streamlit 내 CRUD)
- 권한 관리 (팀별 데이터 접근 제어)
