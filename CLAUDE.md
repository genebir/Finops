# FinOps Platform — 완전 구현 사양서

> 이 문서는 Claude Code가 본 프로젝트를 **처음부터 동일하게 재현**하는 데 필요한 모든 컨텍스트를 담고 있다.
> Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 순서로 구현하며, 각 Phase는 이전 Phase 위에 증분 확장된다.

---

## 1. 프로젝트 목표

로컬 환경에서 돌아가는 **멀티 클라우드 FinOps 플랫폼**을 만든다. 핵심 질문:

1. **"지금 가장 많은 비용을 발생시키는 게 뭐야?"** — Top-N 비용 드라이버 (서비스·리소스·팀·태그별, AWS+GCP+Azure 통합)
2. **"이상하게 튄 비용이 있어?"** — Z-score + IsolationForest + MovingAverage 멀티 탐지기
3. **"예측이랑 실제가 얼마나 달라?"** — Infracost(Terraform 기반) + Prophet(시계열 기반) Variance 분석
4. **"예산 대비 현황은?"** — 팀/환경별 예산 관리, 초과 알림, Chargeback 리포트
5. **"전체 현황을 한눈에 보고 싶다"** — Streamlit 웹 대시보드 (6개 탭)

**확장성 원칙:** `CostSource`, `ForecastProvider`, `AnomalyDetector`, `AlertSink`, `FxProvider` 등 **Protocol 기반 추상화**로 새 클라우드·탐지기·알림을 코드 수정 없이 추가할 수 있어야 한다.

**하드코딩 금지 원칙:** 모든 설정은 `config/settings.yaml` (정적 설정), DuckDB `platform_settings` 테이블 (런타임 임계값), 또는 환경변수로 관리한다. 소스 코드에 수치·경로를 직접 쓰지 않는다.
**디자인 시스템 원칙:** 프론트엔드 작업(Streamlit 대시보드 `scripts/streamlit_app.py`, React 랜딩페이지 `web/`)을 시작하기 전에 **반드시 `docs/design-system.md`를 먼저 읽는다.** 해당 문서는 Streamlit·React 양쪽 구현에 대한 단일 소스 오브 트루스다. 색상(hex), 타이포, border-radius, spacing은 해당 문서의 토큰만 사용하며, Streamlit 기본 테마·Plotly 기본 템플릿·shadcn 기본 스타일을 그대로 쓰지 않는다. 오픈소스 배포 대상 프로젝트이므로 "modern", "clean" 같은 모호한 형용사로 회귀하지 말고 토큰 값 그대로 구현할 것.
**모니터링 웹 앱 원칙:** 신규 웹 모니터링 UI(`web-app/`, `api/`) 작업 시 **반드시 `docs/monitoring-webapp.md`를 먼저 읽는다.** 해당 문서가 페이지 구조·API 엔드포인트·컴포넌트 규칙의 단일 소스 오브 트루스다. 기존 Streamlit(`scripts/streamlit_app.py`)은 내부 디버깅용으로만 유지하며 새 기능은 모두 `web-app/`에 구현한다.

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
| Alerting | slack-sdk (≥3.0) + smtplib | Slack Webhook + 이메일 알림 |
| CLI Dashboard | Rich (≥13.0) | 터미널 대시보드 |
| Web Dashboard | Streamlit (≥1.35) + Plotly (≥5.0) | 웹 대시보드 |
| Standard | FOCUS 1.0 | 비용 데이터 규격 |
| Language | Python 3.14+ | |
| Package Mgmt | uv | |
| Lint/Type | ruff + mypy (strict) | |
| Web Landing | Next.js (≥14) + Tailwind | 오픈소스 랜딩페이지 (web/) |

---

## 3. 전체 아키텍처 (Phase 1~5 완성 상태)

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
│    ┌─────────────────┼──────────────────────────────┐                        │
│    │                 │                   │           │                        │
│    ▼                 ▼                   ▼           ▼                        │
│ [terraform]  [anomaly_detection]  [prophet_forecast] [budget_alerts]          │
│ [infracost]  ZScore+IF+MA멀티탐지   신뢰구간 예측      팀/환경별 예산 관리       │
│    │                 │                   │           │                        │
│    ▼                 ▼                   ▼           ▼                        │
│ [variance]   [alert_dispatch]  [forecast_variance_prophet] [chargeback]       │
│ dim_forecast   anomaly_scores    dim_prophet_forecast       dim_chargeback    │
│    │                 │                   │           │                        │
│    └─────────────────┴───────────────────┴───────────┘                       │
│                        ▼                                                       │
│                 data/reports/*.csv                                             │
│ [fx_rates] → dim_fx_rates (USD 기준 정적 환율)                                 │
│ scripts/dashboard.py      (Rich CLI 대시보드)                                  │
│ scripts/streamlit_app.py  (Streamlit 웹 대시보드, 6탭)                         │
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
│   │   ├── raw_cur_azure.py       # Azure 빌링 생성      [Phase 4]
│   │   ├── bronze_iceberg.py      # AWS Bronze 적재
│   │   ├── bronze_iceberg_gcp.py  # GCP Bronze 적재
│   │   ├── bronze_iceberg_azure.py # Azure Bronze 적재  [Phase 4]
│   │   ├── silver_focus.py        # AWS Silver 정제
│   │   ├── silver_focus_gcp.py    # GCP Silver 정제
│   │   ├── silver_focus_azure.py  # Azure Silver 정제   [Phase 4]
│   │   ├── gold_marts.py          # AWS Gold 마트
│   │   ├── gold_marts_gcp.py      # GCP Gold 마트
│   │   ├── gold_marts_azure.py    # Azure Gold 마트     [Phase 4]
│   │   ├── infracost_forecast.py  # Infracost 예측
│   │   ├── variance.py            # Infracost vs 실제 편차
│   │   ├── anomaly_detection.py   # 멀티 탐지기 이상치 탐지
│   │   ├── alert_dispatch.py      # 알림 발송
│   │   ├── prophet_forecast.py    # Prophet 시계열 예측
│   │   ├── forecast_variance_prophet.py  # Prophet 예측 정확도
│   │   ├── budget_alerts.py       # 예산 사용률 + 초과 알림  [Phase 4]
│   │   ├── chargeback.py          # 팀별 비용 배부 리포트   [Phase 4]
│   │   └── fx_rates.py            # 환율 참조 데이터       [Phase 5]
│   ├── core/
│   │   ├── __init__.py
│   │   ├── cost_source.py         # CostSource Protocol
│   │   ├── forecast_provider.py   # ForecastProvider Protocol + ForecastRecord
│   │   ├── anomaly_detector.py    # AnomalyDetector Protocol + AnomalyResult
│   │   ├── alert_sink.py          # AlertSink Protocol + Alert
│   │   ├── cost_unit.py           # CostUnit 차원
│   │   └── fx_provider.py         # FxProvider Protocol + FxRate  [Phase 5]
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── aws_cur_generator.py   # CostSource 구현체 (가상 AWS)
│   │   ├── gcp_billing_generator.py  # CostSource 구현체 (가상 GCP)
│   │   └── azure_cost_generator.py   # CostSource 구현체 (가상 Azure)  [Phase 4]
│   ├── detectors/
│   │   ├── __init__.py
│   │   ├── zscore_detector.py           # Z-score 탐지기
│   │   ├── isolation_forest_detector.py # IsolationForest 탐지기
│   │   └── moving_average_detector.py   # 이동평균 탐지기  [Phase 5]
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── prophet_provider.py    # ProphetProvider
│   │   └── static_fx_provider.py  # StaticFxProvider    [Phase 5]
│   ├── sinks/
│   │   ├── __init__.py
│   │   ├── console_sink.py        # ConsoleSink
│   │   ├── slack_sink.py          # SlackSink
│   │   └── email_sink.py          # EmailSink (SMTP)    [Phase 5]
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
│   ├── run_phase2.py              # Phase 2 수동 실행 헬퍼
│   └── streamlit_app.py           # Streamlit 웹 대시보드 (6탭)  [Phase 4]
├── data/                          # gitignored
│   ├── warehouse/                 # Iceberg 데이터
│   ├── catalog.db                 # SqlCatalog SQLite
│   ├── marts.duckdb               # DuckDB 파일
│   └── reports/                   # 출력 CSV
└── tests/
    ├── conftest.py
    ├── test_focus_schema.py
    ├── test_cur_generator.py
    ├── test_gcp_generator.py
    ├── test_azure_generator.py
    ├── test_idempotency.py
    ├── test_silver_transforms.py
    ├── test_variance.py
    ├── test_anomaly_detection.py
    ├── test_alert_dispatch.py
    ├── test_prophet_forecast.py
    ├── test_settings_store.py
    ├── test_isolation_forest.py
    ├── test_forecast_variance_prophet.py
    ├── test_budget_alerts.py
    ├── test_chargeback.py
    ├── test_infracost_cli.py
    ├── test_cost_source_protocol.py
    ├── test_supplemental.py
    ├── test_moving_average_detector.py  # [Phase 5]
    ├── test_fx_provider.py              # [Phase 5]
    ├── test_email_sink.py               # [Phase 5]
    ├── test_asset_integration.py        # [Phase 5] Dagster materialize 통합 테스트
    └── test_definitions.py              # [Phase 5]
```

---

## 5. FOCUS 1.0 구현 범위

### 구현 컬럼

- **Identifiers**: `BillingAccountId`, `SubAccountId`, `ResourceId`, `ResourceName`, `ResourceType`
- **Time**: `ChargePeriodStart`, `ChargePeriodEnd`, `BillingPeriodStart`, `BillingPeriodEnd` (UTC)
- **Cost**: `BilledCost`, `EffectiveCost`, `ListCost`, `ContractedCost` — **모두 `Decimal(18,6)`**
- **Currency**: `BillingCurrency` (`USD` 고정)
- **Service**: `ServiceName`, `ServiceCategory`, `ProviderName` (`AWS` | `Google Cloud` | `Microsoft Azure`)
- **Location**: `RegionId`, `RegionName`, `AvailabilityZone` (GCP는 None 허용)
- **Charge**: `ChargeCategory` (Enum: Usage|Purchase|Tax|Credit|Adjustment), `ChargeDescription`
- **Usage**: `UsageQuantity`, `UsageUnit`, `PricingQuantity`, `PricingUnit`
- **SKU**: `SkuId`, `SkuPriceId`
- **Tags**: `Tags` (dict → Pydantic 검증 시 JSON 문자열도 허용, Silver에서 평탄화)

### Tags 정책

모든 리소스(AWS/GCP/Azure 모두)에 반드시 `team`, `product`, `env` 태그를 심는다.
이 세 태그가 `cost_unit_key = team:product:env` 차원의 기초가 된다.

---

## 6. 핵심 추상화 (Protocol 기반)

### 6.1 `CostSource`

```python
# core/cost_source.py
class CostSource(Protocol):
    name: str  # "aws" | "gcp" | "azure"
    resource_id_strategy: str  # "terraform_address"

    def generate(self, period_start: date, period_end: date) -> Iterable[FocusRecord]: ...
```

구현체: `AwsCurGenerator` (seed=42), `GcpBillingGenerator` (seed=84), `AzureCostGenerator` (seed=126)

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
    detector_name: str = "zscore"  # "zscore" | "isolation_forest" | "moving_average"

class AnomalyDetector(Protocol):
    name: str
    def detect(self, df: pl.DataFrame) -> list[AnomalyResult]: ...
```

구현체: `ZScoreDetector`, `IsolationForestDetector`, `MovingAverageDetector`

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

구현체:
- `ConsoleSink` — 항상 활성
- `SlackSink` — `SLACK_WEBHOOK_URL` 환경변수 설정 시
- `EmailSink` — `ALERT_EMAIL_TO` 환경변수 설정 시 (SMTP)

### 6.5 `FxProvider`

```python
# core/fx_provider.py
@dataclass
class FxRate:
    base_currency: str
    target_currency: str
    rate: Decimal
    effective_date: date
    source: str  # "static" | "api"

class FxProvider(Protocol):
    name: str
    def get_rate(self, base: str, target: str, as_of: date | None = None) -> Decimal: ...
    def get_all_rates(self, base: str = "USD") -> list[FxRate]: ...
```

구현체: `StaticFxProvider` (USD 기준 EUR/GBP/KRW/JPY/CNY/SGD/AUD 정적 환율)

### 6.6 `CostUnit` 차원

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
  seed: 42
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
  seed: 84
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

azure_generator:
  seed: 126
  billing_account_id: "AZURE-BILLING-001"
  sub_account_id: "AZURE-SUB-001"
  extra_resources_min: 3
  extra_resources_max: 15
  cost_variation_low: 0.80
  cost_variation_high: 1.20
  anomaly_multiplier_low: 4.0
  anomaly_multiplier_high: 7.0
  list_price_markup: 1.10

azure_iceberg:
  bronze_table: "focus.bronze_cur_azure"
  silver_table: "focus.silver_focus_azure"

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

budget_defaults:
  entries:
    - team: "platform"
      env: "prod"
      amount: 5000.0
    - team: "*"
      env: "staging"
      amount: 1000.0
    - team: "*"
      env: "*"
      amount: 2000.0

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
| `ALERT_EMAIL_TO` | (직접 읽기) | 알림 수신 이메일 (쉼표 구분) |
| `SMTP_HOST` | (직접 읽기) | SMTP 서버 주소 |
| `SMTP_PORT` | (직접 읽기) | SMTP 포트 (기본 587) |
| `SMTP_USER` | (직접 읽기) | SMTP 인증 사용자 |
| `SMTP_PASSWORD` | (직접 읽기) | SMTP 인증 비밀번호 |
| `ALERT_EMAIL_FROM` | (직접 읽기) | 발신자 이메일 |

### 7.4 DuckDB `platform_settings` 테이블

`SettingsStoreResource.ensure_table()`이 최초 실행 시 아래 기본값으로 seed한다. 이미 존재하는 키는 덮어쓰지 않는다.

```
anomaly.zscore.warning              = 2.0
anomaly.zscore.critical             = 3.0
variance.threshold.over_pct         = 20.0
variance.threshold.under_pct        = 20.0
alert.critical_deviation_pct        = 50.0
alert.slack_timeout_sec             = 10
reporting.lookback_days             = 30
reporting.top_resources_limit       = 20
reporting.top_cost_units_limit      = 10
infracost.subprocess_timeout_sec    = 120
anomaly.active_detectors            = "zscore,isolation_forest"
isolation_forest.contamination      = 0.05
isolation_forest.n_estimators       = 100
isolation_forest.random_state       = 42
isolation_forest.score_critical     = -0.20
isolation_forest.score_warning      = -0.05
budget.alert_threshold_pct          = 80.0
budget.over_threshold_pct           = 100.0
moving_average.window_days          = 7
moving_average.multiplier_warning   = 2.0
moving_average.multiplier_critical  = 3.0
moving_average.min_window           = 3
arima.order_p                       = 1
arima.order_d                       = 1
arima.order_q                       = 1
arima.threshold_warning             = 2.0
arima.threshold_critical            = 3.0
arima.min_samples                   = 10
```

런타임 변경 (Dagster 재시작 불필요):
```sql
UPDATE platform_settings SET value = '3.0' WHERE key = 'anomaly.zscore.warning';
UPDATE platform_settings SET value = 'zscore,moving_average' WHERE key = 'anomaly.active_detectors';
UPDATE platform_settings SET value = '70.0' WHERE key = 'budget.alert_threshold_pct';
```

---

## 8. 주요 설계 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| **fact_daily_cost 통합** | `provider` 컬럼으로 AWS+GCP+Azure 단일 테이블 | 멀티 클라우드 집계를 단일 쿼리로 처리 |
| **Gold 마트 멱등성** | `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE provider=? AND month=?` + `INSERT` | `CREATE OR REPLACE`는 타 provider 데이터를 삭제함 |
| **anomaly_scores 멱등성** | `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE month=?` + `INSERT` | 동일 방식 |
| **dim_prophet_forecast 멱등성** | `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE resource_id IN (...)` + `INSERT` | Prophet은 모든 히스토리로 학습 후 resource 단위 교체 |
| **dim_cost_unit** | `CREATE OR REPLACE TABLE AS SELECT FROM fact_daily_cost` | 전체 재생성이 안전하고 빠름 |
| **Infracost 조인 키** | CUR ResourceId를 `aws_instance.web_1` 형식으로 심어 자동 매칭 | terraform 리소스 주소와 일치 |
| **IsolationForest 최소 샘플** | 10개 미만 그룹 건너뜀 | 모델 안정성 |
| **MovingAverage std=0 처리** | 윈도우 std가 0이면서 현재값이 다를 경우 critical로 처리 | constant background에서 spike 탐지 가능 |
| **Prophet 신뢰구간** | `yhat_lower`/`yhat_upper` 존재 여부 체크 후 사용 | mock 테스트에서 해당 컬럼이 없을 수 있음 |
| **Gold 마트 _INSERT_FACT_SQL** | `gold_marts.py`에 상수로 정의, gcp/azure에서 import | 3개 클라우드가 동일 INSERT 로직 공유 |
| **flatten_tags 공유** | `utils/silver_transforms.py`에 `flatten_tags()` 정의 | AWS/GCP/Azure silver asset이 동일 로직 사용 |
| **Bronze/Silver 스키마 공유** | GCP/Azure asset이 `bronze_iceberg.py`의 스키마 상수 import | 스키마 중복 제거 |
| **load_config lru_cache** | `@lru_cache(maxsize=1)` — 테스트는 `clear_config_cache` fixture로 초기화 | `conftest.py`에 `autouse=False` fixture 제공 |
| **BudgetStore 와일드카드 우선순위** | `(team, env)` > `(team, "*")` > `("*", env)` > `("*", "*")` | team 특정 설정이 env 특정 설정보다 우선 |
| **FX 환율** | StaticFxProvider로 USD 기준 8개 통화 정적 환율 제공 | Phase 6에서 실시간 API로 교체 가능 |
| **통화** | USD 고정 (FX는 Phase 5에서 참조 테이블로 추가) | |
| **시간대** | 모든 timestamp UTC | Silver에서 `ChargePeriodStartUtc` 컬럼 유지 |
| **Cost 타입** | `Decimal(18,6)` | float 절대 금지 |
| **통합 테스트** | `dagster.materialize()` + tmp_path 기반 실제 Iceberg/DuckDB | asset 코드 직접 실행 — mock 없이 실제 경로 커버 |

---

## 9. 중요 구현 주의사항 (반드시 지킬 것)

1. **asset 파일에 `from __future__ import annotations` 금지**
   Dagster가 런타임에 타입 힌트를 검사하는데, `from __future__ import annotations`가 있으면 `AssetExecutionContext`를 문자열로 처리해 `DagsterInvalidDefinitionError`가 발생한다.
   → 모든 `assets/` 디렉토리 파일에 해당.

2. **DuckDB `ON CONFLICT DO UPDATE SET updated_at = CURRENT_TIMESTAMP` 금지**
   DuckDB는 `CURRENT_TIMESTAMP`를 컬럼명으로 인식하여 Binder Error가 발생한다.
   → `settings_store.py`에서 `SELECT` 후 조건부 `UPDATE`/`INSERT` 패턴 사용.

3. **`platform_settings` ALTER TABLE 마이그레이션**
   새 컬럼 추가 시:
   ```python
   conn.execute("ALTER TABLE anomaly_scores ADD COLUMN IF NOT EXISTS detector_name VARCHAR DEFAULT 'zscore'")
   ```

4. **Silver asset은 Bronze 전체를 읽고 월로 필터링**
   PyIceberg가 `scan().to_polars()`로 파티션 푸시다운을 하지 않으므로 Python 레벨에서 월 필터링 수행:
   ```python
   df = df.filter(pl.col("ChargePeriodStart").dt.to_string("%Y-%m").str.starts_with(month_str))
   ```

5. **Prophet mock 테스트**
   `yhat_lower`/`yhat_upper` 컬럼 없는 mock DataFrame으로 테스트할 때 `ProphetProvider`가 graceful fallback:
   ```python
   lower_sum = float(horizon_rows["yhat_lower"].sum()) if "yhat_lower" in horizon_rows.columns else 0.0
   ```

6. **통합 테스트에서 빈 fact_daily_cost 테이블 주의**
   DuckDB에서 빈 테이블 쿼리 결과로 `pl.from_arrow()` 호출 시 `ValueError: Must pass schema` 발생 가능.
   → 최소 1개 이상의 행을 seed하거나, 테이블 미존재 케이스만 테스트할 것.

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
    "streamlit>=1.35",
    "plotly>=5.0",
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

## 11. 코딩 컨벤션

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
- **프론트엔드 작업 시** `docs/design-system.md`의 디자인 토큰 외 값 사용 금지
- **Streamlit** (`scripts/streamlit_app.py`): 커스텀 CSS는 `_inject_design_system()` 함수에 집중. Plotly는 프로젝트 전용 template `"finops"` 정의 후 모든 차트에 적용
- **React** (`web/`): Tailwind 사용, CSS 변수는 `globals.css`에 design-system.md의 토큰 그대로 정의. shadcn 기본 스타일 금지
- 상태값(anomaly severity, variance, budget status) 색상은 `design-system.md`의 Semantic Color Mapping 준수
- Provider 구분(AWS/GCP/Azure)은 브랜드 원색 금지 — muted 팔레트 사용
- 금액 표시: JetBrains Mono + tabular-nums, `$` 기호는 숫자보다 작게
- 이모지 아이콘 금지 (Phosphor Icons 또는 인라인 SVG)
---

## 12. 멱등성 체크리스트

- [x] AWS/GCP/Azure CUR 생성기 seed 고정 시 동일 출력
- [x] Iceberg Bronze는 파티션 단위 `overwrite` (append 금지)
- [x] `fact_daily_cost`: `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE provider=? AND month=?` + `INSERT`
- [x] `anomaly_scores`: `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE month=?` + `INSERT`
- [x] `dim_prophet_forecast`: `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE resource_id IN (...)` + `INSERT`
- [x] `dim_budget_status`: `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE billing_month=?` + `INSERT`
- [x] `dim_chargeback`: `CREATE TABLE IF NOT EXISTS` + `DELETE WHERE billing_month=?` + `INSERT`
- [x] `dim_fx_rates`: `DELETE WHERE base_currency='USD'` + `INSERT`
- [x] `dim_cost_unit`: `CREATE OR REPLACE TABLE AS SELECT FROM fact_daily_cost` (전체 재생성)
- [x] `v_top_resources_30d`, `v_top_cost_units_30d`, `v_variance`: `CREATE OR REPLACE VIEW`
- [x] 전체 파이프라인 2회 실행 후 동일 결과

---

## 13. 실행 방법

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
uv run python scripts/dashboard.py --month 2024-01

# 웹 대시보드 (Streamlit)
uv run streamlit run scripts/streamlit_app.py

# 테스트 (커버리지 포함)
uv run pytest --cov=dagster_project --cov-fail-under=90

# 린트 / 타입 체크
uv run ruff check .
uv run mypy dagster_project
```

---

## 14. Phase별 구현 히스토리

### Phase 1 — Medallion 아키텍처 기반

- AWS CUR → Bronze(Iceberg) → Silver → Gold(DuckDB) 파이프라인
- FOCUS 1.0 Pydantic 스키마, CostSource Protocol
- Infracost 예측 + Variance 분석
- Terraform 샘플 (EC2/RDS/S3)

### Phase 2 — 이상치 탐지·알림·Prophet 예측

- `ZScoreDetector`, `ConsoleSink`, `SlackSink`
- `ProphetProvider` (시계열 예측, 신뢰구간 포함)
- `SettingsStoreResource` (DuckDB `platform_settings`)
- `alert_dispatch` asset

### Phase 3 — GCP 파이프라인 + IsolationForest + Rich 대시보드

- `GcpBillingGenerator` (seed=84), GCP Bronze/Silver/Gold 파이프라인
- `IsolationForestDetector` (scikit-learn)
- `forecast_variance_prophet` asset (Prophet 예측 정확도)
- `scripts/dashboard.py` (Rich CLI 대시보드)

### Phase 4 — Azure + 예산 관리 + Streamlit 대시보드

- `AzureCostGenerator` (seed=126, azurerm_* ResourceId)
- `BudgetStoreResource` — DuckDB `dim_budget`, `(team, env)` 와일드카드 지원
- `budget_alerts` asset — `dim_budget_status`, warning/over 알림
- `chargeback` asset — `dim_chargeback`, 팀별 비용 배부
- `scripts/streamlit_app.py` — 6탭 웹 대시보드 (Overview/Explorer/Anomalies/Forecast/Budget/Chargeback)
- **272 tests, 70.23% → baseline**

### Phase 5 — FX 환율 + MovingAverage + EmailSink + 90% 커버리지

- `StaticFxProvider` + `FxProvider` Protocol + `fx_rates` asset → `dim_fx_rates`
- `MovingAverageDetector` — 롤링 이동평균, std=0 spike 탐지 지원
- `EmailSink` — SMTP 기반 이메일 AlertSink (`ALERT_EMAIL_TO` 환경변수 활성)
- `anomaly_detection.py` — `moving_average` 탐지기 활성화 지원 추가
- `test_asset_integration.py` — `dagster.materialize` 기반 통합 테스트 37개
- **272 tests, 95.71% coverage** ✅

### Phase 6 — ARIMA 탐지기 + HTTP FX Provider + Prophet CV + Budget CRUD UI

- `ArimaDetector` — statsmodels ARIMA 잔차 기반 이상치 탐지, graceful ImportError 처리
- `anomaly_detection.py` — `arima` 탐지기 통합 (`anomaly.active_detectors` 설정으로 제어)
- `settings_store.py` — ARIMA 파라미터 6개 신규 설정 (order_p/d/q, threshold, min_samples)
- `HttpFxProvider` — open.er-api.com 실시간 환율, `EXCHANGE_RATE_API_KEY` env, StaticFxProvider 폴백
- `ProphetProvider.cross_validate()` — prophet.diagnostics 기반 MAE/RMSE/MAPE 자동 평가
- `streamlit_app.py` — Budget CRUD UI (Add/Update/Delete 예산 항목)
- **298 tests, 94.93% coverage** ✅

### Phase 7 — Autoencoder 탐지기 + 비용 추천 엔진 + Settings UI

- `AutoencoderDetector` — sklearn MLPRegressor 재구성 오차 기반 이상치 탐지 (슬라이딩 윈도우 autoencoder)
- `anomaly_detection.py` — `autoencoder` 탐지기 통합
- `settings_store.py` — autoencoder 파라미터 5개 신규 설정 (window_size, thresholds, min_samples, max_iter)
- `cost_recommendations` asset — 비용 최적화 추천 3가지 규칙 (idle/high_growth/persistent_anomaly) → `dim_cost_recommendations`
- `streamlit_app.py` — Settings 탭 추가 (platform_settings CRUD + active detectors 토글 + recommendations 표시)
- **311 tests, 94.56% coverage** ✅

### Phase 8 — 디자인 시스템 + Streamlit 개선

- `docs/design-system.md` — Arc Browser 기반 디자인 토큰 단일 소스 (Warm palette, Squircle, Instrument Serif)
- `scripts/streamlit_app.py` — `_inject_design_system()` + Plotly `"finops"` template + 탭 이모지 제거
- `.streamlit/config.toml` — Warm palette (primaryColor `#D97757`, bg `#FAF7F2`)
- **311 tests, 94.56% coverage** (Python 파이프라인 무변경) ✅
- 참고: Next.js 랜딩페이지(`web/`)는 이 단계에서 프로토타입으로 제작했다가 Phase 8.1에서 대시보드 앱으로 방향 전환하면서 삭제함

### Phase 8.1 — FastAPI + Next.js 대시보드 MVP

- `api/main.py` — FastAPI 서버, `/api/overview` 엔드포인트 (DuckDB 직접 읽기, CORS 포함)
  - 응답: `period_start/end`, `total_cost`, `cost_by_team[]`, `top_resources[]`, `anomaly_count`, `resource_count`
- `web-app/` — Next.js 14 대시보드 앱 (포트 3002), 디자인 토큰 동일 적용
  - `app/(dashboard)/layout.tsx` — 사이드바 레이아웃
  - `app/(dashboard)/overview/page.tsx` — Server Component, SSR, StatCard/TeamBar/EnvBadge
  - `app/(dashboard)/overview/data.ts` — `fetchOverview()` + 타입 정의
- `deploy.sh` / `start.sh` / `stop.sh` — 전체 서비스 원커맨드 운영
  - 서비스 구성: Dagster(3000), Streamlit(8501), FastAPI(8000), Dashboard(3002)
- **311 tests, 94.56% coverage** (Python 파이프라인 무변경) ✅

---

## 15. Phase 9 — 대시보드 확장

Phase 8.1에서 Overview 페이지 MVP가 검증됐다. Phase 9는 나머지 핵심 뷰를 API + 페이지 단위로 증분 추가한다.

### 추가할 API 엔드포인트 (`api/main.py`)

| 엔드포인트 | 데이터 소스 | 핵심 응답 |
|---|---|---|
| `GET /api/anomalies` | `anomaly_scores` | severity별 목록, resource/team 필터 |
| `GET /api/forecast` | `dim_forecast`, `dim_prophet_forecast` | resource별 예측 vs 실제 |
| `GET /api/budget` | `dim_budget_status` | 팀/env별 예산 사용률, over/warning 목록 |
| `GET /api/cost-explorer` | `fact_daily_cost` | 날짜·team·service·env 필터링, 일별 시계열 |
| `GET /api/recommendations` | `dim_cost_recommendations` | 규칙별 추천 목록 |

### 추가할 대시보드 페이지 (`web-app/app/(dashboard)/`)

| 경로 | 설명 |
|---|---|
| `anomalies/page.tsx` | 이상치 목록, severity 배지, detector 이름 |
| `forecast/page.tsx` | 예측 vs 실제 비교 테이블 |
| `budget/page.tsx` | 팀별 예산 게이지 바, 초과/경고 하이라이트 |
| `cost-explorer/page.tsx` | 날짜 범위 + team/env 필터, 일별 비용 바 차트 |
| `recommendations/page.tsx` | idle/high_growth/persistent_anomaly 카드 |

### 설계 원칙

- **API**: 모든 엔드포인트는 `api/main.py` 단일 파일 유지. 라우터 분리는 엔드포인트 10개 초과 시.
- **페이지**: 각 페이지는 Server Component 기본. 필터·인터랙션 필요 시만 `"use client"` 분리.
- **데이터 fetch**: `next: { revalidate: 60 }` — 1분 캐시, 실시간 필요 없음.
- **차트**: 순수 CSS/SVG 또는 경량 라이브러리. Recharts/Chart.js 중 하나만 선택 시 도입.
- **사이드바**: `layout.tsx`에서 링크 목록을 배열로 관리, 페이지 추가 시 배열에만 추가.

### 구현 순서

1. `GET /api/anomalies` + `anomalies/page.tsx`
2. `GET /api/budget` + `budget/page.tsx`
3. `GET /api/cost-explorer` + `cost-explorer/page.tsx` (필터 포함)
4. `GET /api/forecast` + `forecast/page.tsx`
5. `GET /api/recommendations` + `recommendations/page.tsx`
6. 사이드바 활성 링크 하이라이트 (`usePathname`)

### 장기 과제 (Phase 10+)

- 실제 클라우드 API 연동 (AWS CUR S3, GCP Billing Export, Azure Cost Management)
- 팀별 데이터 접근 제어 (인증)
- 이메일 AlertSink Streamlit 설정 UI