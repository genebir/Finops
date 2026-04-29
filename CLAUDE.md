# FinOps Platform — 완전 구현 사양서

> 이 문서는 Claude Code가 본 프로젝트를 **처음부터 동일하게 재현**하는 데 필요한 모든 컨텍스트를 담고 있다.
> Phase 1 → … → Phase 40 순서로 구현하며, 각 Phase는 이전 Phase 위에 증분 확장된다.
> **현재 상태:** Phase 42 완료 — Environment Detail 드릴다운 `/api/environments/{env}` + `/environments/[env]` 페이지 + Env Breakdown 링크 연결, **651 tests pass**.

---

## 1. 프로젝트 목표

로컬 환경에서 돌아가는 **멀티 클라우드 FinOps 플랫폼**을 만든다. 핵심 질문:

1. **"지금 가장 많은 비용을 발생시키는 게 뭐야?"** — Top-N 비용 드라이버 (서비스·리소스·팀·태그별, AWS+GCP+Azure 통합)
2. **"이상하게 튄 비용이 있어?"** — Z-score + IsolationForest + MovingAverage 멀티 탐지기
3. **"예측이랑 실제가 얼마나 달라?"** — Infracost(Terraform 기반) + Prophet(시계열 기반) Variance 분석
4. **"예산 대비 현황은?"** — 팀/환경별 예산 관리, 초과 알림, Chargeback 리포트
5. **"전체 현황을 한눈에 보고 싶다"** — Streamlit 웹 대시보드 (6개 탭)

**확장성 원칙:** `CostSource`, `ForecastProvider`, `AnomalyDetector`, `AlertSink`, `FxProvider` 등 **Protocol 기반 추상화**로 새 클라우드·탐지기·알림을 코드 수정 없이 추가할 수 있어야 한다.

**하드코딩 금지 원칙:** 모든 설정은 `config/settings.yaml` (정적 설정), PostgreSQL `platform_settings` 테이블 (런타임 임계값), 또는 환경변수로 관리한다. 소스 코드에 수치·경로를 직접 쓰지 않는다.
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
| Analytics DB | PostgreSQL (≥14) + psycopg2 | Silver→Gold 집계, 분석 마트, 런타임 설정 |
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
│   ├── streamlit_app.py           # Streamlit 웹 대시보드 (6탭)  [Phase 4]
│   ├── init_db.py                 # DB 스키마 부트스트랩 CLI     [Phase 12]
│   └── setup.py                   # 멱등 개발환경 셋업 (--all로 전체 부트스트랩)  [Phase 40.1]
├── api/                           # FastAPI 백엔드              [Phase 8.1+]
│   ├── main.py                    # 앱 엔트리 (CORS, 라우터 등록)
│   ├── deps.py                    # db_read/db_write 컨텍스트매니저
│   ├── models/                    # Pydantic 요청/응답 모델
│   └── routers/                   # 도메인별 API 라우터 (30+개)
├── web-app/                       # Next.js 14 대시보드          [Phase 8.1+]
│   ├── app/(dashboard)/           # 30개 페이지 (i18n EN/KO)
│   ├── components/                # 공유 컴포넌트 (Card, MetricCard, Sidebar 등)
│   └── lib/                       # API 클라이언트, i18n, 타입
├── data/                          # gitignored
│   ├── warehouse/                 # Iceberg 데이터
│   ├── catalog.db                 # SqlCatalog SQLite
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
환경변수                       ← CI/CD, 시크릿, PostgreSQL 접속 정보
PostgreSQL platform_settings   ← 런타임 임계값 (Dagster 재시작 불필요, 웹 UI에서 CRUD)
```

### 7.2 `config/settings.yaml` 전체 구조

```yaml
postgres:
  host: "localhost"
  port: 5432
  dbname: "finops"
  user: "finops_app"
  password: "finops_secret_2026"

data:
  warehouse_path: "data/warehouse"
  catalog_db_path: "data/catalog.db"
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
| `POSTGRES_HOST` | `postgres.host` | PostgreSQL 호스트 (기본 localhost) |
| `POSTGRES_PORT` | `postgres.port` | PostgreSQL 포트 (기본 5432) |
| `POSTGRES_DBNAME` | `postgres.dbname` | PostgreSQL DB 이름 (기본 finops) |
| `POSTGRES_USER` | `postgres.user` | PostgreSQL 사용자 (기본 finops_app) |
| `POSTGRES_PASSWORD` | `postgres.password` | PostgreSQL 비밀번호 |
| `CUR_SEED` | `cur_generator.seed` | AWS CUR 생성 시드 |
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

### 7.4 PostgreSQL `platform_settings` 테이블

`SettingsStoreResource.ensure_table()`이 최초 실행 시 아래 기본값으로 seed한다. 이미 존재하는 키는 덮어쓰지 않는다(`ON CONFLICT (key) DO NOTHING`). 웹 UI에서 CRUD로 관리 가능.

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

런타임 변경 (Dagster 재시작 불필요 — SQL 직접 또는 웹 UI에서 CRUD):
```sql
-- PostgreSQL 직접 수정
UPDATE platform_settings SET value = '3.0', updated_at = NOW() WHERE key = 'anomaly.zscore.warning';

-- 또는 웹 UI (Settings 페이지)에서 인라인 편집/신규 추가/삭제 가능
-- API: GET/POST/PUT/DELETE /api/settings[/{key}]
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
| **통합 테스트** | `dagster.materialize()` + tmp_path 기반 실제 Iceberg/PostgreSQL | asset 코드 직접 실행 — mock 없이 실제 경로 커버 |
| **DB 마이그레이션** | DuckDB → PostgreSQL (Phase 11) | 멀티 프로세스 동시 접근, 웹 CRUD, 트랜잭션 안정성 |
| **DB 접근 (Dagster)** | `DuckDBResource.get_connection()` → psycopg2 커넥션 | 이름은 레거시, 실제로는 PostgreSQL 접속 |
| **DB 접근 (API)** | `api/deps.py` `db_read()`/`db_write()` → psycopg2 | autocommit=True, 읽기/쓰기 분리 |
| **SQL 구문** | PostgreSQL 표준 | `to_char()`, `DOUBLE PRECISION`, `%s` 파라미터, `DROP VIEW IF EXISTS` + `CREATE VIEW` |
| **Settings CRUD** | PostgreSQL `platform_settings` + FastAPI POST/PUT/DELETE + Next.js UI | 웹에서 실시간 설정 관리, Dagster 재시작 불필요 |

---

## 9. 중요 구현 주의사항 (반드시 지킬 것)

1. **asset 파일에 `from __future__ import annotations` 금지**
   Dagster가 런타임에 타입 힌트를 검사하는데, `from __future__ import annotations`가 있으면 `AssetExecutionContext`를 문자열로 처리해 `DagsterInvalidDefinitionError`가 발생한다.
   → 모든 `assets/` 디렉토리 파일에 해당.

2. **PostgreSQL SQL 구문 주의사항**
   - `?` 바인딩 금지 → `%s` 사용 (psycopg2)
   - `DOUBLE` → `DOUBLE PRECISION`
   - `::VARCHAR` → `::TEXT`
   - `strftime(col, '%Y-%m')` → `to_char(col, 'YYYY-MM')`
   - `CREATE OR REPLACE VIEW` → `DROP VIEW IF EXISTS` + `CREATE VIEW` (컬럼 변경 시 에러)
   - `ROUND(double_col, 2)` → `ROUND(CAST(col AS NUMERIC), 2)` (PostgreSQL `round(dp, int)` 미지원)
   - SQL SELECT에서 `CAST()`/`ROUND()` 사용 시 **반드시 `AS alias`** 명시 (PostgreSQL이 컬럼명을 `round`, `cast` 등으로 반환)

3. **PostgreSQL 테이블/뷰 존재 확인**
   ```sql
   SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='table_name'
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

6. **통합 테스트 — 공유 PostgreSQL DB 주의**
   테스트가 실제 PostgreSQL에 직접 접속한다 (DuckDB in-memory 격리 불가).
   - 테스트 데이터는 `test_` 또는 `inttest_` 접두사를 써서 프로덕션 데이터와 구분
   - fixture에서 반드시 cleanup (`DELETE WHERE resource_id LIKE 'test_%'`)
   - 와일드카드 `("*", "*")` 같은 글로벌 행이 다른 테스트에 영향 주의

7. **PostgreSQL 오브젝트 소유권**
   테이블/뷰는 `finops_app` 사용자가 소유해야 한다. `postgres` 사용자로 생성된 오브젝트는 `ALTER TABLE/VIEW ... OWNER TO finops_app` 필요.

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
    "psycopg2-binary>=2.9",
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
- [x] `dim_cost_unit`: `DELETE` + `INSERT INTO ... SELECT FROM fact_daily_cost` (전체 재생성)
- [x] `v_top_resources_30d`, `v_top_cost_units_30d`, `v_variance`: `DROP VIEW IF EXISTS` + `CREATE VIEW`
- [x] 전체 파이프라인 2회 실행 후 동일 결과

---

## 13. 실행 방법

```bash
# 부트스트랩
uv sync
cp .env.example .env

# 원커맨드 개발환경 셋업 (테이블 생성 + 시드 + asset 실행 + 뷰 생성)
uv run python scripts/setup.py --all
# 또는 개별 단계:
uv run python scripts/setup.py --status        # 현재 상태 확인
uv run python scripts/setup.py --tables        # 테이블만 생성
uv run python scripts/setup.py --seed          # 설정·예산 시드
uv run python scripts/setup.py --materialize   # Dagster asset 실행
uv run python scripts/setup.py --views         # SQL 뷰 생성

# Infracost CLI 설치 (선택)
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh
infracost configure set api_key <YOUR_KEY>

# Dagster 실행
uv run dagster dev
# → http://localhost:3000 → 전체 assets materialize

# 모니터링 대시보드 (Next.js + FastAPI)
cd web-app && npm run dev    # → http://localhost:3002
uv run uvicorn api.main:app  # → http://localhost:8000

# 터미널 대시보드 (Rich CLI)
uv run python scripts/dashboard.py --month 2024-01

# 웹 대시보드 (Streamlit, 내부 디버깅용)
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

### Phase 9 — 대시보드 확장 (anomalies/forecast/budget/cost-explorer/recommendations)

- `api/main.py` — Phase 8.1 위에 5개 엔드포인트 추가 (단일 파일 유지)
- `web-app/app/(dashboard)/` — 5개 페이지 추가, 사이드바 활성 링크 하이라이트
- **311 tests, 94.56% coverage** (Python 파이프라인 무변경) ✅

### Phase 10 — API 아키텍처 리팩토링 + Budget CRUD + 대시보드 UX

- `api/main.py` — 슬림 엔트리 (CORS 확장 GET/POST/PUT/DELETE, `/health` 추가)
- `api/deps.py` — `db_read`/`db_write` 컨텍스트매니저, 쓰기 락 백오프 retry
- `api/models/`, `api/routers/` — 라우터·모델 분리 (FastAPI 표준 구조)
- Budget CRUD: POST/PUT/DELETE `/api/budget[/entries]` + 409 중복 감지
- Settings PUT (기존 키만 갱신), `/api/filters` 단일 드롭다운 엔드포인트
- Cost Explorer: provider 필터 + `by_provider[]`, Chargeback: `available_months` 월 선택
- 모든 동적 쿼리 파라미터 바인딩 (SQL 인젝션 방지)
- Frontend: BudgetManager CRUD UI, Settings 인라인 편집, CostExplorer 필터 확장, Chargeback 월 셀렉터
- **311 tests, 94.56% coverage** (Python 파이프라인 무변경) ✅

### Phase 11 — DuckDB → PostgreSQL 전면 마이그레이션

- 전체 DB 레이어를 DuckDB(파일 기반)에서 PostgreSQL(서버 기반)로 전환 (28+ 파일)
- `dagster_project/resources/duckdb_io.py` — psycopg2 기반 `get_connection()` (이름은 레거시 유지)
- `dagster_project/resources/settings_store.py` — psycopg2, `ON CONFLICT DO NOTHING` seed
- `dagster_project/resources/budget_store.py` — psycopg2
- `dagster_project/assets/*.py` — `%s` 파라미터, `to_char()`, `DOUBLE PRECISION`, `DROP VIEW IF EXISTS`
- `api/deps.py` — psycopg2 `db_read()`/`db_write()`, `tables()`, `columns()` 헬퍼
- `api/routers/*.py` — cursor 패턴, `%s`, `::TEXT`, `CAST AS DOUBLE PRECISION`
- `scripts/dashboard.py`, `streamlit_app.py`, `run_phase2.py` — psycopg2 전환
- `sql/marts/*.sql` — `DOUBLE PRECISION`, `INTERVAL '30 days'`, `DELETE+INSERT` 패턴
- `tests/*.py` — 실제 PostgreSQL, unique prefix + cleanup fixture
- `config/settings.yaml` — `postgres:` 섹션 추가 (host/port/dbname/user/password)
- **288 tests pass** ✅

### Phase 11.1 — Settings 풀 CRUD + 대시보드 UX 개선

- Settings API — POST (201, 409 on conflict) + DELETE (204) 엔드포인트 추가
- `SettingCreateRequest` Pydantic 모델 (key/value/value_type/description)
- `SettingsStoreResource` — `delete_setting()` 메서드, `db_path` 필드 제거
- Settings UI — "Add Setting" 폼 + 삭제 확인 + Type 컬럼 표시
- 테이블 헤더 간격 정렬 — 8개 테이블 `<th>` 수평 패딩을 `<td>`와 일치
- Badge/pill 컬럼 가운데 정렬 — Env/Severity/Status/Source 컬럼 `textAlign: "center"`
- `variance.py` — `ROUND()` 결과에 `AS variance_pct` 별칭 추가 (KeyError 수정)
- **288 tests pass** ✅

### Phase 12 — 옵스 관측성 (Observability & Ops)

- `dagster_project/db_schema.py` — 중앙 집중 DDL 스토어 + `ensure_tables()` / `ensure_base_tables()` / `init_db.py`
- `pipeline_run_log` 테이블 — Dagster run 성공/실패 로그 (run_id, asset_key, partition_key, status, duration_sec, row_count, error_message)
- `dagster_project/sensors/run_logger.py` — `pipeline_run_success_sensor` / `pipeline_run_failure_sensor` (run_status_sensor + run_failure_sensor)
- `dagster_project/definitions.py` — sensors 등록
- `api/routers/ops.py` — `/api/ops/runs`, `/api/ops/health`, `/api/ops/live`, `/api/ops/ready`, `/api/ops/metrics`
- `/api/ops/metrics` — Prometheus text format (finops_table_rows, finops_anomalies_active_30d, finops_budgets_over, finops_database_up 등)
- `api/middleware.py` — `RequestContextMiddleware` (x-request-id 헤더, JSON access log)
- `web-app/app/(dashboard)/ops/` — OpsClient (10초 자동 새로고침), KPI 카드 4개, Recent Runs 테이블, Table Health 테이블
- `install.sh` — 크로스플랫폼 원커맨드 인스톨러 (macOS/Debian/RHEL/Arch/Alpine), uv sync + PostgreSQL 부트스트랩 + npm build
- `scripts/init_db.py` — DB 스키마 부트스트랩 CLI (ensure_base_tables + platform_settings seed)
- 모든 asset 파일에 `ensure_tables()` 추가 → 신규 머신 자가치유 멱등성
- `tests/test_api_ops.py` (8개), `tests/test_run_logger.py` (3개) 추가
- **299 tests pass** ✅

### Phase 13 — 데이터 품질 검증 + CSV Export

- `dagster_project/assets/data_quality.py` — `data_quality` asset
  - 10개 자동 검증 규칙: `min_rows` / `no_negatives` / `null_ratio`
  - fact_daily_cost, anomaly_scores, dim_prophet_forecast, dim_budget, dim_chargeback, dim_fx_rates 검증
  - 결과를 `dim_data_quality` 테이블에 저장 (7일 롤링 보존)
- `dagster_project/db_schema.py` — `dim_data_quality` DDL 추가
- `dagster_project/definitions.py` — `data_quality` asset 등록
- `api/routers/data_quality.py` — `/api/data-quality` (최신 체크 결과), `/api/export/{table}` (CSV 다운로드)
  - 9개 테이블 CSV export 지원 (최대 100k 행)
  - 알 수 없는 테이블은 404
- `web-app/app/(dashboard)/data-quality/` — DataQualityClient (30초 자동 새로고침)
  - KPI 카드 4개 (Total/Passed/Failed/Health)
  - 체크 결과 테이블 (All / Failed 필터)
  - CSV Export 링크 목록
- 사이드바에 "Data Quality" 항목 추가
- `tests/test_data_quality.py` (10개) 추가
- **309 tests pass** ✅

### Phase 14 — 번 레이트 모니터링 + Dagster 스케줄

- `dagster_project/assets/burn_rate.py` — `burn_rate` asset
  - 현재/전월 (team, env) 단위 MTD 비용, 일평균, 월말 예상 비용 계산
  - `dim_budget`와 조인해 `projected_utilization` 산출 (critical/warning/on_track/no_budget)
  - `dim_burn_rate` 테이블에 DELETE+INSERT 멱등 저장
- `dagster_project/db_schema.py` — `dim_burn_rate` DDL 추가
- `dagster_project/schedules/monthly.py` — Dagster 스케줄 2개
  - `monthly_burn_rate_schedule` — 매월 2일 06:00 UTC
  - `daily_data_quality_schedule` — 매일 07:00 UTC (기본 STOPPED)
- `dagster_project/definitions.py` — `burn_rate` asset + schedules 등록
- `api/routers/burn_rate.py` — `GET /api/burn-rate?billing_month=YYYY-MM`
  - items 목록 + summary (total_mtd, projected_eom, critical/warning/on_track count)
- `web-app/app/(dashboard)/burn-rate/page.tsx` — Server Component, BurnBar 게이지, 상태 배지
- 사이드바에 "Burn Rate" 항목 추가
- `tests/test_burn_rate.py` (8개) 추가
- **317 tests pass** ✅

### Phase 15 — 리소스 인벤토리 + 태그 완성도

- `dagster_project/assets/resource_inventory.py` — `resource_inventory` asset
  - `fact_daily_cost` 전체를 resource_id 단위로 집계 → `dim_resource_inventory`
  - `team` / `product` / `env` 3개 필수 태그 완성도 검증 (`tags_complete`, `missing_tags`)
  - ON CONFLICT (resource_id) DO UPDATE — 점진 upsert
  - `total_cost_30d` — 최근 30일 비용 집계
- `dagster_project/db_schema.py` — `dim_resource_inventory` DDL (PRIMARY KEY resource_id)
- `dagster_project/definitions.py` — `resource_inventory` asset 등록
- `api/routers/inventory.py` — `GET /api/inventory`
  - 필터: provider / team / env / tags_complete
  - 응답: items + summary (total, complete, incomplete, completeness_pct)
- `tests/test_resource_inventory.py` (10개) 추가
- **327 tests pass** ✅

### Phase 16 — 태그 정책 엔진 + 위반 추적

- `dagster_project/assets/tag_policy.py` — `tag_policy` asset
  - `_DEFAULT_POLICY`: 서비스 카테고리별 필수 태그 규칙 (`*` 와일드카드 지원)
  - `platform_settings.tag_policy.rules` JSON으로 런타임 정책 교체 가능
  - `dim_tag_violations` — 당일 위반 DELETE+INSERT, cost_30d 기준 severity 산출 (1000+ → critical, 다중 누락 → critical)
- `dagster_project/db_schema.py` — `dim_tag_violations` DDL 추가
- `dagster_project/resources/settings_store.py` — `tag_policy.rules` 기본 설정 추가
- `dagster_project/definitions.py` — `tag_policy` asset 등록
- `api/routers/tag_policy.py` — `GET /api/tag-policy`
  - 필터: severity / provider / missing_tag
  - 응답: violations + summary (total, critical, warning)
- `tests/test_tag_policy.py` (13개) 추가
- **340 tests pass** ✅

### Phase 17 — 비용 배분 (Cost Allocation)

- `dagster_project/assets/cost_allocation.py` — `cost_allocation` asset
  - `dim_allocation_rules` 테이블에서 분할 규칙 로드 (resource_id → [(team, split_pct)])
  - 규칙에 매칭되는 리소스의 일별 비용을 팀 단위로 비례 분할
  - `dim_allocated_cost` — DELETE(resource_ids) + INSERT 멱등 저장
  - `allocation_type`: split (다중 팀) / full (단일 팀)
- `dagster_project/db_schema.py` — `dim_allocation_rules` + `dim_allocated_cost` DDL 추가
- `api/routers/cost_allocation.py` — 전체 CRUD + 조회
  - `GET /api/cost-allocation/rules` — 규칙 목록
  - `POST /api/cost-allocation/rules` (201) — 신규 규칙 (split_pct 0<x≤100 검증)
  - `PUT /api/cost-allocation/rules/{id}` — 규칙 수정
  - `DELETE /api/cost-allocation/rules/{id}` (204) — 규칙 삭제
  - `GET /api/cost-allocation?team=X&billing_month=YYYY-MM` — 배분된 비용 조회
- `tests/test_cost_allocation.py` (11개) 추가
- **351 tests pass** ✅

### Phase 18 — Showback 리포트 + JSON Export

- `dagster_project/assets/showback_report.py` — `showback_report` asset
  - 팀별 MTD 비용, 예산 사용률, 이상치 건수, Top-3 서비스/리소스 집계
  - `dim_showback_report` — JSONB 컬럼(top_services/top_resources), DELETE+INSERT 멱등
  - 현재 + 전월 2개월 계산
- `dagster_project/db_schema.py` — `dim_showback_report` DDL (JSONB) 추가
- `api/routers/showback.py` — `/api/showback` (조회) + `/api/showback/export` (JSON 다운로드)
  - `billing_month` / `team` 필터, Content-Disposition 헤더
- `tests/test_showback_report.py` (9개) 추가
- **360 tests pass** ✅

### Phase 19 — 비용 트렌드 분석 + 기간 비교

- `dagster_project/assets/cost_trend.py` — `cost_trend` asset
  - 모든 가용 월에 대해 (provider, team, env, service) 단위 월별 비용 롤업
  - `dim_cost_trend` — DELETE+INSERT 멱등 (월 단위)
  - `anomaly_scores`와 조인해 월별 이상치 건수 포함
- `dagster_project/db_schema.py` — `dim_cost_trend` DDL 추가
- `api/routers/cost_trend.py` — 트렌드 + 비교 엔드포인트
  - `GET /api/cost-trend?provider=X&team=Y&env=Z&months=12` — 시계열 (최대 36개월)
  - `GET /api/cost-trend/compare?period1=YYYY-MM&period2=YYYY-MM` — 기간 비교, MoM change%, 팀별 증감
  - summary: latest_cost, mom_change_pct, avg_monthly_cost
- `tests/test_cost_trend.py` (11개) 추가
- **371 tests pass** ✅

### Phase 20 — 알림 히스토리 영속화 + Acknowledge 워크플로우

- `dagster_project/assets/alert_dispatch.py` — 발송 후 `dim_alert_history`에 INSERT
  - `psycopg2.extras.execute_values()` 배치 INSERT
  - `ensure_tables(conn, "dim_alert_history")` 자체 부트스트랩
- `dagster_project/db_schema.py` — `dim_alert_history` DDL 추가 (id BIGSERIAL PK, acknowledged, acknowledged_at, acknowledged_by)
- `api/routers/alerts.py` — 알림 히스토리 엔드포인트
  - `GET /api/alerts?severity=X&acknowledged=false&alert_type=Y&limit=N` — 필터링 + 페이지네이션
  - `POST /api/alerts/{id}/acknowledge` — acknowledge 워크플로우 (acknowledged_by 기록)
  - summary: critical/warning/info/unacknowledged 집계
- `api/main.py` — `alerts` 라우터 등록
- `tests/test_alert_history.py` (13개) 추가
- **384 tests pass** ✅

### Phase 21 — Alerts 대시보드 페이지

- `web-app/lib/types.ts` — `AlertHistoryItem`, `AlertSummary`, `AlertHistoryData` 타입 추가
- `web-app/lib/api.ts` — `api.alerts()`, `api.acknowledgeAlert()` 메서드 추가
- `web-app/app/(dashboard)/alerts/AlertsClient.tsx` — 클라이언트 컴포넌트
  - KPI 카드: Critical / Warning / Info / Open(미확인) 건수
  - severity 필터 (all/critical/warning/info), "Open only" 토글
  - 테이블: 리소스·타입·실제비용·편차·발생시간·ACK/OPEN 상태
  - "Ack" 버튼 → POST /api/alerts/{id}/acknowledge → 즉시 반영
- `web-app/app/(dashboard)/alerts/page.tsx` — 페이지 래퍼
- `web-app/app/(dashboard)/Sidebar.tsx` — "Alerts" 내비 항목 추가
- **384 tests pass** (프론트엔드 추가, Python 무변경) ✅

### Phase 22 — 멀티클라우드 비교 API + Cloud Compare 대시보드

- `api/routers/cloud_compare.py` — `GET /api/cloud-compare?billing_month=YYYY-MM&team=X`
  - provider별 총비용·리소스 수·점유율
  - provider별 상위 5개 서비스
  - provider별 최근 6개월 월별 트렌드
  - 팀별 provider 교차 비용 (team × provider 매트릭스)
- `api/main.py` — `cloud_compare` 라우터 등록
- `tests/test_cloud_compare.py` (11개) — 응답 형태·집계·정렬 검증
- `web-app/app/(dashboard)/cloud-compare/page.tsx` — Server Component
  - KPI 카드: AWS / GCP / Azure 비용 + 막대 게이지 + 점유율
  - Provider별 상위 서비스 표
  - 팀별 provider 교차 테이블
  - 3-컬럼 sparkbar 트렌드
- `web-app/app/(dashboard)/Sidebar.tsx` — "Cloud Compare" 항목 추가
- **395 tests pass** ✅

### Phase 23 — 절감 실적 추적 (Savings Tracker)

- `dagster_project/db_schema.py` — `dim_savings_realized` DDL 추가
  - resource_id별 예상 절감액 vs 전월 대비 실제 절감액 비교
  - status: `realized` / `partial` / `pending` / `cost_increased`
- `dagster_project/assets/savings_tracker.py` — `savings_tracker` asset
  - `dim_cost_recommendations` 기반, 전월 대비 `fact_daily_cost` 비용 비교
  - 80% 이상 실현 시 `realized`, 부분 실현 시 `partial`, 비용 증가 시 `cost_increased`
  - DELETE+INSERT 멱등 (billing_month 단위)
- `dagster_project/definitions.py` — `savings_tracker` 등록
- `api/routers/savings.py` — `GET /api/savings?billing_month=X&team=Y&status=Z`
  - summary: total_estimated, total_realized, realized/partial/pending/cost_increased 건수
- `api/main.py` — `savings` 라우터 등록
- `tests/test_savings_tracker.py` (10개) 추가
- **405 tests pass** ✅

### Phase 24 — Savings 대시보드 페이지 + Cost Heatmap API

- `api/routers/cost_heatmap.py` — `GET /api/cost-heatmap?billing_month=X&provider=Y&team=Z`
  - 일별·팀별 비용 매트릭스 반환 (rows=teams, cols=dates, values=cost)
  - max_cost 포함 — 클라이언트 정규화 용이
- `api/main.py` — `cost_heatmap` 라우터 등록
- `tests/test_cost_heatmap.py` (10개) — 형태·정합성·날짜 순서 검증
- `web-app/app/(dashboard)/savings/page.tsx` — Server Component
  - KPI 카드: 예상 절감액 / 실현 절감액 / 실현율% / 추천 수
  - 상태 요약 pill (Realized/Partial/Pending/Cost Increased)
  - 전체 추천별 표 (resource, 예상/실현/전월/현재 비용, StatusBadge)
- `web-app/lib/types.ts` — `SavingsItem`, `SavingsSummary`, `SavingsData`, `CostHeatmapData`, `HeatmapRow` 타입 추가
- `web-app/lib/api.ts` — `api.savings()`, `api.costHeatmap()` 메서드 추가
- `web-app/app/(dashboard)/Sidebar.tsx` — "Savings" 항목 추가
- **415 tests pass** ✅

### Phase 25 — 비용-리스크 상관 API

- `api/routers/cost_risk.py` — `GET /api/cost-risk?billing_month=X&provider=Y&team=Z&min_anomaly_count=N&limit=M`
  - 리소스별 총비용 × 이상치 빈도 기반 risk_score 계산 (정규화 곱)
  - `anomaly_scores` 테이블 없을 경우 graceful fallback (has_anomaly_data=false)
  - summary: total_resources, total_cost, total_anomalies, has_anomaly_data
- `api/main.py` — `cost_risk` 라우터 등록
- `tests/test_cost_risk.py` (10개) 추가
- **425 tests pass** ✅

### Phase 26 — Risk 대시보드 + 리소스 드릴다운 API

- `api/routers/resource_detail.py` — `GET /api/resources/{resource_id}?months=N`
  - 리소스별 월별 비용 히스토리 (최대 N개월, 데이터 최신일 기준 앵커)
  - 최근 30일 일별 비용
  - 이상치 이력 (anomaly_scores 없으면 빈 배열)
  - summary: total_cost, avg_monthly_cost, latest_month_cost, anomaly_count, months_tracked
- `web-app/app/(dashboard)/risk/page.tsx` — Server Component
  - KPI 카드: 리소스 수 / 총비용 / 이상치 이벤트 수
  - 상위 위험 리소스 callout (risk_score > 0)
  - 전체 리소스 표: 팀·provider·서비스·비용·이상치수·RiskBar
- `web-app/app/(dashboard)/Sidebar.tsx` — "Risk" 항목 추가
- `tests/test_resource_detail.py` (9개) 추가
- **434 tests pass** ✅

### Phase 27 — 팀 리더보드 + 서비스 카테고리 브레이크다운 API

- `api/routers/leaderboard.py` — `GET /api/leaderboard?billing_month=X&provider=Y&limit=N`
  - 팀별 당월/전월 비용, MoM change%, 총비용 점유율, 리소스 수
  - 순위(rank) 필드 포함, 순서는 당월 비용 내림차순
- `api/routers/service_breakdown.py` — `GET /api/service-breakdown?billing_month=X&team=Y&provider=Z`
  - service_category별 집계 (by_category)
  - 서비스명별 top 15 (by_service)
  - grand_total, pct 포함
- `api/main.py` — 두 라우터 등록
- `tests/test_leaderboard.py` (15개) 추가
- **449 tests pass** ✅

### Phase 28 — Leaderboard + Services 대시보드 페이지

- `web-app/app/(dashboard)/leaderboard/page.tsx` — Server Component
  - KPI 카드: 총지출 (MoM badge), 팀 수, 전월 지출
  - 순위 표: #(메달), 팀명, 당월/전월 비용, MoM%, 점유율 bar, 리소스 수
- `web-app/app/(dashboard)/services/page.tsx` — Server Component
  - service_category별 가로 PctBar 목록 (색상 팔레트)
  - 상위 15 서비스 표 (서비스명, 카테고리, 비용, %)
- `web-app/app/(dashboard)/Sidebar.tsx` — "Leaderboard", "Services" 항목 추가
- **449 tests pass** (프론트엔드 추가, Python 무변경) ✅

### Phase 29 — 예산 예측 asset + /api/budget-forecast

- `dagster_project/db_schema.py` — `dim_budget_forecast` DDL 추가
  - 팀/환경별 선형 외삽 EOM 예측 + ±20% 신뢰구간
  - risk_level: `normal` / `warning`(80%+) / `over`(100%+)
- `dagster_project/assets/budget_forecast.py` — `budget_forecast` asset
  - 데이터 최신 billing_month 자동 감지
  - `budget_store.get_budget(team, env)` 로 예산 조회 후 projected_pct 계산
  - DELETE+INSERT 멱등
- `dagster_project/definitions.py` — `budget_forecast` 등록
- `api/routers/budget_forecast.py` — `GET /api/budget-forecast?billing_month=X&team=Y&risk_level=Z`
  - summary: total_projected_eom, over/warning/normal 건수
- `api/main.py` — `budget_forecast` 라우터 등록
- `tests/test_budget_forecast.py` (10개) 추가
- **459 tests pass** ✅

### Phase 30 — Budget Forecast 대시보드 + /api/env-breakdown

- `web-app/app/(dashboard)/budget-forecast/page.tsx` — Server Component
  - KPI 카드: 예상 EOM 합계, Over/Warning/On-track 건수
  - 표: 팀·환경, 진행 ProjectionBar (MTD/예상/예산/경과일 마커), 신뢰구간, 예산, 예상%, RiskBadge
- `web-app/app/(dashboard)/Sidebar.tsx` — "Budget Forecast" 항목 추가
- `api/routers/env_breakdown.py` — `GET /api/env-breakdown?billing_month=X&provider=Y`
  - 환경별 집계 (env, cost, resource_count, team_count, pct)
  - env × team 교차표 (cross_tab)
- `api/main.py` — `env_breakdown` 라우터 등록
- `tests/test_env_breakdown.py` (9개) 추가
- **468 tests pass** ✅

### Phase 31 — Tag Compliance Score + Env Breakdown 대시보드

- `dagster_project/assets/tag_compliance_score.py` — `tag_compliance_score` asset
  - `dim_resource_inventory` + `dim_tag_violations` 조인으로 team×provider 준수율 점수 계산
  - 점수 공식: 태그 완성도% - 위반 패널티(위반당 5점, 최대 30점)
  - `dim_tag_compliance` — DELETE+INSERT 멱등 (billing_month 단위), 순위(rank) 포함
- `dagster_project/db_schema.py` — `dim_tag_compliance` DDL 추가
- `api/routers/tag_compliance.py` — `GET /api/tag-compliance?billing_month=X&provider=Y&team=Z`
  - 응답: billing_month, summary(avg_score, perfect_count, below_threshold_count, total_teams), teams[]
  - 테이블 미존재 시 자동 생성 (graceful bootstrap)
- `api/routers/env_breakdown.py` 기반 `web-app/app/(dashboard)/env-breakdown/page.tsx` — Server Component
  - KPI 카드 4개, 환경별 비용 바, env×team 교차 테이블
- `web-app/app/(dashboard)/tag-compliance/page.tsx` — Server Component
  - KPI 카드 4개, 팀별 준수율 점수 표, 색상 기반 점수 게이지
- `tests/test_tag_compliance.py` (10개) 추가
- **477 tests pass** ✅

### Phase 32 — Anomaly Timeline + Cloud Config + 디자인 통일

- `api/routers/anomaly_timeline.py` — `GET /api/anomaly-timeline?months=N&provider=Y&team=Z&severity=S`
  - anomaly_scores 기반 월별 시계열, MAX(charge_date) 앵커로 안정적 집계
  - provider 필터: `resource_id IN (SELECT DISTINCT resource_id FROM fact_daily_cost WHERE provider=%s)` 서브쿼리
  - 응답: series[], top_teams[], summary
- `api/routers/cloud_config.py` — Cloud 연동 설정 API
  - `GET /api/cloud-config` — provider별 전체 설정 반환
  - `PUT /api/cloud-config` — 단일 키 업데이트 (provider/key/value 검증)
  - `GET /api/cloud-config/status` — enabled/configured/missing_keys 상태
- `dagster_project/resources/settings_store.py` — 클라우드 설정 15개 기본값 추가 (cloud.aws.*, cloud.gcp.*, cloud.azure.*)
- `web-app/app/(dashboard)/anomaly-timeline/page.tsx` — Server Component, 월별 이상치 시계열 표
- `web-app/app/(dashboard)/settings/CloudConfigClient.tsx` — 클라이언트 컴포넌트
  - AWS/GCP/Azure 카드, 활성화 토글, 인라인 편집, 시크릿 env var 힌트
- `web-app/app/(dashboard)/settings/page.tsx` — CloudConfigClient 추가
- **디자인 통일 (전면 점검)**:
  - `web-app/components/layout/PageHeader.tsx` — 28px 타이틀로 통일 (clamp 제거)
  - `web-app/components/layout/Sidebar.tsx` (실제 파일) — 20개 플랫 메뉴 → 5개 카테고리 그룹 드롭다운
    - Costs / Anomalies / Budget / Compliance / Operations 그룹
    - `useEffect`로 현재 경로 그룹 자동 열림
  - 9개 페이지 전면 재작성: budget-forecast, cloud-compare, leaderboard, risk, services, savings, env-breakdown, tag-compliance, anomaly-timeline
    - `var(--bg-card)`, `var(--text-muted)`, `var(--accent)` → 올바른 토큰으로 교체
    - 인라인 h1 → `<PageHeader>`, 커스텀 div → `<Card>/<CardHeader>`, KPI → `<MetricCard>`
    - 표 헤더 패딩 패턴 통일
- `docs/ui-components.md` — 디자인 통일성 가이드 (단일 소스 오브 트루스)
  - CSS 토큰 표, 금지 패턴, 컴포넌트 사용 규칙, 표준 테이블 패턴, 페이지 구조 템플릿
- `tests/test_cloud_config.py` (11개) 추가
- `tests/test_anomaly_timeline.py` (10개) 추가
- **498 tests pass** ✅

### Phase 33 — Inventory / Showback / Tag Policy 대시보드 페이지

- `web-app/app/(dashboard)/inventory/page.tsx` — Server Component
  - KPI 카드: 총 리소스, 태그 완성, 불완전, 완성도%
  - 전체 리소스 표: Resource/Service/Provider/Team/Env/30d Cost/Tags
  - Tags OK / missing: {tag} pill 표시 (tool tip 포함)
- `web-app/app/(dashboard)/showback/page.tsx` — Server Component
  - KPI 카드: 총비용, 팀 수, 예산 초과 팀, 이상치 수
  - 팀 요약 표: Total Cost / Budget / 진행률 bar / 이상치
  - 팀별 상세 카드 그리드: Top Services + Top Resources 목록
  - "Export JSON" 버튼 → `/api/showback/export` 직접 다운로드
- `web-app/app/(dashboard)/tag-policy/page.tsx` — Server Component
  - KPI 카드: 총 위반, Critical, Warning, 리스크 비용(30d)
  - 위반 표: Resource/Provider/Team/Env/Missing Tag(코드 스타일 pill)/Severity/30d Cost
- `web-app/app/(dashboard)/burn-rate/page.tsx` — 재작성 (디자인 수정)
  - `var(--bg-card)`, `var(--font-mono)`, `var(--border-subtle)` → 올바른 토큰으로 수정
  - TypeScript 오류 수정: `BurnRateSummary` 타입 명시적 사용
  - `MetricCard`, `Card`, `CardHeader`, `EmptyState` 컴포넌트 사용
- `web-app/components/layout/Sidebar.tsx` — Compliance 그룹에 tag-policy, inventory 추가; Budget 그룹에 showback 추가
  - `Package`, `ClipboardText`, `Prohibit` 아이콘 추가 (@phosphor-icons/react)
- `web-app/app/(dashboard)/data-quality/DataQualityClient.tsx` — TypeScript 오류 수정 (`CardHeader style` prop 제거)
- **498 tests pass** ✅ (Python 파이프라인 무변경)

### Phase 34 — Cost Trend 대시보드 페이지

- `web-app/app/(dashboard)/cost-trend/page.tsx` — Server Component
  - KPI 카드: Latest Month, Latest Cost, MoM Change%, Avg Monthly
  - 월별 가로 바 차트 (TrendBar: 최대값 기준 정규화)
  - Monthly Detail 표: billing_month / total_cost / resources / anomalies
  - Period Comparison 섹션: 최근 2개월 자동 비교
    - 요약 행: period1 → period2 총비용, 전체 변화액, MoMBadge
    - 팀×환경×provider 상세 표: period1/period2 비용, 변화액, Δ% 뱃지
- `web-app/components/layout/Sidebar.tsx` — Costs 그룹에 `/cost-trend` 추가 (TrendUp 아이콘)
- **498 tests pass** ✅ (Python 파이프라인 무변경)

### Phase 35 — Resource Detail 드릴다운 페이지

- `web-app/app/(dashboard)/resources/[id]/page.tsx` — 동적 Server Component
  - KPI 카드: Total Cost, Avg Monthly, Latest Month, Anomaly Count
  - Daily Cost 바 차트 (최근 30일, maxCost 기준 정규화)
  - Monthly History 표: billing_month / cost / team / env pill
  - Anomaly History 표: date / cost / z-score σ / severity pill / detector
  - ← Inventory 돌아가기 링크
- `web-app/app/(dashboard)/inventory/page.tsx` — 리소스명에 `/resources/{id}` 링크 추가
- **498 tests pass** ✅ (Python 파이프라인 무변경)

### Phase 36 — Cost Allocation 대시보드 페이지

- `web-app/app/(dashboard)/cost-allocation/page.tsx` — Server Component
  - KPI 카드: 규칙 수, 고유 리소스, 팀 수, 총 배분 금액
  - `AllocationClient` + 초기 데이터 전달
- `web-app/app/(dashboard)/cost-allocation/AllocationClient.tsx` — 클라이언트 컴포넌트
  - Allocation Rules 표: resource_id / team / split% (인라인 편집) / description / Edit+Delete 버튼
  - "Add Rule" 인라인 폼 (resource_id / team / split% / description)
  - 삭제 확인 (Check/X 패턴)
  - Allocated Costs 표: team / resource / service / provider / split% / allocated / original 비용
- `web-app/components/layout/Sidebar.tsx` — Budget 그룹에 `/cost-allocation` 추가 (Rows 아이콘)
- **498 tests pass** ✅ (Python 파이프라인 무변경)

### Phase 37 — API 엔드포인트 테스트 보강 (커버리지 92%)

저커버리지 API 라우터(15~40%)에 TestClient 기반 테스트 7개 파일 추가:

- `tests/test_api_overview.py` (10개) — /api/overview: 200, shape, total_cost, cost_by_team, top_resources, provider/date 필터
- `tests/test_api_anomalies.py` (9개) — /api/anomalies: 200, shape, severity 필터, team 필터, item 필드, limit
- `tests/test_api_filters.py` (7개) — /api/filters: 200, shape, providers 알려진 값, billing_months 정렬, date_range
- `tests/test_api_cost_explorer.py` (10개) — /api/cost-explorer: 200, shape, daily/service/provider 필드, team/provider/env/date 필터
- `tests/test_api_budget.py` (8개) — /api/budget + entries + CRUD 왕복 (create→update→delete, 409 중복)
- `tests/test_api_settings.py` (8개) — /api/settings + 풀 CRUD 왕복, 409/404 에러
- `tests/test_api_forecast.py` (6개) — /api/forecast: shape, totals, item 필드, source 값, bounds 순서
- `tests/test_api_chargeback.py` (7개) — /api/chargeback: shape, totals, by_team 필드, pct 합계, billing_month 필터
- `tests/test_api_recommendations.py` (6개) — /api/recommendations: shape, rule_type 값, potential_savings

결과: **570 tests pass, API 커버리지 92%** ✅

### Phase 38 — Overview 페이지 강화

- `web-app/app/(dashboard)/overview/page.tsx` — Server Component 전면 개선
  - `fetchProviderCosts()` — `/api/cost-explorer` `by_provider` 데이터로 클라우드별 비용 breakdown 카드 추가
  - `fetchRecentTrend()` — `/api/cost-trend?months=6` 데이터로 6개월 sparkline 바 차트 추가
  - `Promise.all([fetchProviderCosts(), fetchRecentTrend()])` 병렬 fetch
  - Top Resources 표: resource_id → `/resources/{id}` 드릴다운 링크 (Link 컴포넌트)
  - Provider breakdown: `ProviderBadge` + 비용 + pct% + 진행 바
  - Trend sparkline: MoM change badge (isUp: critical/healthy 색상), "View full trend →" 링크
  - 레이아웃: Row 1 (teams 2fr + provider 1fr), Row 2 (resources 3fr + trend 2fr)
  - `export const dynamic = "force-dynamic"` + `PROVIDER_COLORS` CSS 변수 매핑

- **570 tests pass** ✅

### Phase 39 — Cost Heatmap + Cloud Config 대시보드

- `web-app/app/(dashboard)/cost-heatmap/page.tsx` — Server Component
  - `/api/cost-heatmap` 데이터로 팀 × 일자 CSS grid 히트맵 렌더링
  - `heatColor()` — 값 비율에 따라 `rgb(59,46,34) → rgb(217,119,87)` 색상 보간
  - 날짜 헤더 + 팀 행 + 일별 합계 행 + 컬러 범례
  - 피크 날짜 callout (vs 월평균 대비 증감%)
  - KPI: 총비용 / 팀 수 / 데이터 일수 / 팀당 평균
- `web-app/app/(dashboard)/cloud-config/CloudConfigClient.tsx` — Client Component
  - AWS/GCP/Azure 3개 provider 섹션 (Enabled 토글 + field 인라인 편집)
  - `PUT /api/cloud-config` 호출로 즉시 저장 (Enter 저장, Escape 취소)
  - `GET /api/cloud-config/status` 로 missing_keys 피드백 표시
- `web-app/app/(dashboard)/cloud-config/page.tsx` — Server Component 래퍼
  - `Promise.all([fetchConfig(), fetchStatus()])` 병렬 fetch
  - KPI: 활성 provider 수 / 완전 설정 수 / 누락 필드 수
- `Sidebar.tsx` — "Cost Heatmap", "Cloud Config" 항목 추가
- `tests/test_api_cost_heatmap.py` (10개) — shape/max/dates정렬/team필터 검증
- `tests/test_api_cloud_config.py` (11개) — GET/PUT/status/에러 검증

- **591 tests pass** ✅

### Phase 40 — Team Detail API + 드릴다운 페이지

- `api/routers/team_detail.py` — `GET /api/teams/{team}?months=N`
  - 404 반환 (팀 미존재 시)
  - `monthly_trend`: 최근 N개월 팀 비용 + 리소스 수 시계열
  - `by_service`: 당월 서비스별 비용 Top-10 + pct
  - `by_env`: 당월 환경별 비용 + pct
  - `by_provider`: 당월 provider별 비용 + pct
  - `top_resources`: 당월 리소스별 비용 Top-10
  - `anomalies`: 최근 이상치 10건 (anomaly_scores 없으면 빈 배열)
  - `summary`: curr_cost, prev_cost, mom_change_pct, resource_count, anomaly_count
- `api/main.py` — `team_detail` 라우터 등록
- `api/routers/__init__.py` — `team_detail` 추가
- `web-app/app/(dashboard)/teams/[team]/page.tsx` — Server Component
  - ← Leaderboard 뒤로 링크
  - KPI 카드 4개 (당월 비용, MoM%, 리소스 수, 이상치 수)
  - 6개월 trend sparkline 바 차트
  - 환경별 + Provider별 TrendBar
  - Top Services 표 + Top Resources 표 (resource_id → `/resources/{id}` 링크)
  - 최근 이상치 테이블 (SeverityBadge, z-score, 리소스 링크)
- `web-app/app/(dashboard)/leaderboard/page.tsx` — 팀명 → `/teams/{team}` 링크 추가
- `tests/test_api_team_detail.py` (10개) — shape/404/sorted/pct/months param 검증

- **601 tests pass** ✅

### Phase 40.1 — 프로덕션 준비 + 멱등 셋업 스크립트

- `scripts/setup.py` — 멱등 개발환경 셋업 스크립트 (신규)
  - CLI: `--status`, `--tables`, `--seed`, `--materialize`, `--views`, `--all`, `--force`
  - 7개 ASSET_GROUPS 순서대로 `dagster.materialize()` 실행 (Bronze→Silver→Gold→Analysis→Derived→Alerts→Quality)
  - 22개 asset→테이블 매핑으로 완료 여부 자동 감지 (스킵 가능)
  - PostgreSQL 테이블/뷰 자동 생성, platform_settings + dim_budget 시드
  - 컬러 터미널 출력 (✓ pass / ✗ fail / → skip)
- **i18n 완성** — 서버 컴포넌트 30개 페이지 전체 하드코딩 문자열 제거
  - `budget/page.tsx` — 3개 문자열 번역 (empty hint, no budget set)
  - `tag-compliance/page.tsx` — ScoreBadge i18n (High/Medium/Low → `t("misc.*")`)
  - `showback/page.tsx` — empty state description 번역
  - `BudgetManager.tsx`, `DataQualityClient.tsx`, `AllocationClient.tsx` — `useT()` 훅으로 클라이언트 컴포넌트 번역
- **페이지 메타데이터** — 23개 페이지에 `export const metadata = { title: "PageName — FinOps" }` 추가
- **레이아웃 표준화** — 6개 페이지 `maxWidth` 1000px/1100px → 1200px 통일
- **반응형 테이블** — `globals.css`에 `.table-responsive` + `@media (max-width: 768px)` 추가
- `overview/data.ts` — 중복 `API_BASE` 제거, `@/lib/api` import로 통일
- `test_tag_compliance.py` — `test_tag_compliance_rank_sequence` assertion 완화 (실제 데이터 호환)
- **631 tests pass** ✅

### Phase 41 — Service Detail 드릴다운

- `api/routers/service_detail.py` — `GET /api/services/{service_name}?months=N`
  - 404 반환 (서비스 미존재 시)
  - `monthly_trend`: 최근 N개월 서비스별 비용 + 리소스 수
  - `by_team`: 당월 팀별 비용 Top-10 + pct
  - `by_provider`: 당월 provider별 비용 + pct
  - `by_env`: 당월 환경별 비용 + pct
  - `top_resources`: 당월 리소스별 비용 Top-10
  - `summary`: curr_cost, prev_cost, mom_change_pct, resource_count, team_count
- `api/main.py` — `service_detail` 라우터 등록
- `api/routers/__init__.py` — `service_detail` 추가
- `web-app/app/(dashboard)/services/[service]/page.tsx` — Server Component
  - ← Services 뒤로 링크
  - KPI 카드 4개 (당월 비용, MoM%, 리소스 수, 팀 수)
  - 6개월 trend sparkline 바 차트
  - 환경별 + Provider별 TrendBar
  - By Team 표 (팀명 → `/teams/{team}` 링크) + Top Resources 표 (resource_id → `/resources/{id}` 링크)
- `web-app/app/(dashboard)/services/page.tsx` — 서비스명에 `/services/{service}` 링크 추가
- `web-app/lib/i18n/translations.ts` — service_detail 관련 i18n 키 추가
- `tests/test_api_service_detail.py` (10개) — shape/404/sorted/pct/months param 검증

- **641 tests pass** ✅

### Phase 42 — Environment Detail 드릴다운

- `api/routers/env_detail.py` — `GET /api/environments/{env}?months=N`
  - 404 반환 (환경 미존재 시)
  - `monthly_trend`: 최근 N개월 환경별 비용 + 리소스 수
  - `by_team`: 당월 팀별 비용 + pct (전체)
  - `by_provider`: 당월 provider별 비용 + pct
  - `by_service`: 당월 서비스별 비용 Top-10 + pct
  - `top_resources`: 당월 리소스별 비용 Top-10
  - `summary`: curr_cost, prev_cost, mom_change_pct, resource_count, team_count
- `api/main.py` — `env_detail` 라우터 등록
- `api/routers/__init__.py` — `env_detail` 추가
- `web-app/app/(dashboard)/environments/[env]/page.tsx` — Server Component
  - ← Env Breakdown 뒤로 링크
  - KPI 카드 4개 (당월 비용, MoM%, 리소스 수, 팀 수)
  - 6개월 trend sparkline 바 차트 (env 색상 토큰 적용: prod orange, staging purple, dev blue, test green)
  - 팀별/Provider별 TrendBar (팀명 → `/teams/{team}` 링크)
  - Top Services 표 (서비스명 → `/services/{service}` 링크)
  - Top Resources 표 (resource_id → `/resources/{id}` 링크)
- `web-app/app/(dashboard)/env-breakdown/page.tsx` — env 뱃지에 `/environments/{env}` 링크 (cost-by-env + cost-matrix 양쪽)
- `web-app/lib/i18n/translations.ts` — `page.env_detail.desc` 키 추가
- `tests/test_api_env_detail.py` (10개) — shape/404/sorted/pct/months param 검증

- **651 tests pass** ✅

---

## 15. 현재 대시보드 페이지 현황 (Phase 42 기준)

### 구현 완료된 페이지 및 연결 API

| 경로 | API 엔드포인트 | 설명 |
|---|---|---|
| `/overview` | `/api/overview`, `/api/cost-explorer`, `/api/cost-trend` | KPI 4개, 팀별 비용 바, provider 비용, 6개월 트렌드 |
| `/cost-explorer` | `/api/cost-explorer`, `/api/filters` | 일별 비용 바 차트, team/provider/env/date 필터 |
| `/anomalies` | `/api/anomalies` | 이상치 목록, severity/team 필터, detector 이름 |
| `/forecast` | `/api/forecast` | Prophet/Infracost 예측 vs 실제, 신뢰구간 |
| `/budget` | `/api/budget`, `/api/budget/entries` | 팀별 예산 게이지, BudgetManager CRUD UI |
| `/recommendations` | `/api/recommendations` | idle/high_growth/persistent_anomaly 추천 카드 |
| `/chargeback` | `/api/chargeback` | 팀별 비용 배부, 월 선택 필터 |
| `/ops` | `/api/ops/runs`, `/api/ops/health` | Pipeline 실행 로그, 테이블 헬스, Prometheus metrics |
| `/data-quality` | `/api/data-quality`, `/api/export/{table}` | 자동 검증 결과, CSV export 링크 |
| `/burn-rate` | `/api/burn-rate` | MTD/EOM 예상, 팀·환경별 게이지 바 |
| `/alerts` | `/api/alerts`, `/api/alerts/{id}/acknowledge` | severity 필터, Ack 워크플로우 |
| `/cloud-compare` | `/api/cloud-compare` | provider별 비용/점유율/서비스/팀 매트릭스 |
| `/savings` | `/api/savings` | 절감 실적 추적, realized/partial/pending 상태 |
| `/risk` | `/api/cost-risk` | 리소스 비용×이상치 risk score 매트릭스 |
| `/leaderboard` | `/api/leaderboard` | 팀 비용 순위, MoM badge, 팀명 → `/teams/{team}` 링크 |
| `/services` | `/api/service-breakdown` | 카테고리별·서비스명별 비용 분석 |
| `/budget-forecast` | `/api/budget-forecast` | 팀별 EOM 예측 + 신뢰구간, risk badge |
| `/env-breakdown` | `/api/env-breakdown` | 환경별 교차표, 팀×환경 cost 매트릭스 |
| `/tag-compliance` | `/api/tag-compliance` | 팀별 태그 준수율 점수, 색상 게이지 |
| `/anomaly-timeline` | `/api/anomaly-timeline` | 월별 이상치 시계열, top 팀 집계 |
| `/settings` | `/api/settings`, `/api/cloud-config` | 플랫폼 설정 CRUD + Cloud 연결 설정 섹션 |
| `/inventory` | `/api/inventory` | 리소스 인벤토리, 태그 완성도, `/resources/{id}` 링크 |
| `/showback` | `/api/showback`, `/api/showback/export` | 팀별 쇼백 리포트, JSON export |
| `/tag-policy` | `/api/tag-policy` | 태그 위반 목록, missing tag 코드 pill |
| `/cost-trend` | `/api/cost-trend`, `/api/cost-trend/compare` | 월별 바 차트, 기간 비교 섹션 |
| `/cost-allocation` | `/api/cost-allocation/rules`, `/api/cost-allocation` | 배분 규칙 CRUD, 배분된 비용 조회 |
| `/cost-heatmap` | `/api/cost-heatmap` | 팀 × 일자 CSS grid 히트맵, 피크 날짜 callout |
| `/cloud-config` | `/api/cloud-config`, `/api/cloud-config/status` | AWS/GCP/Azure 연결 설정 인라인 편집 |
| `/resources/[id]` | `/api/resources/{resource_id}` | 리소스 드릴다운: 일별 비용, 월별 히스토리, 이상치 |
| `/teams/[team]` | `/api/teams/{team}` | 팀 드릴다운: 트렌드, 서비스/환경/provider 분석, 리소스 |
| `/services/[service]` | `/api/services/{service_name}` | 서비스 드릴다운: 트렌드, 팀/환경/provider 분석, 리소스 |
| `/environments/[env]` | `/api/environments/{env}` | 환경 드릴다운: 트렌드, 팀/서비스/provider 분석, 리소스 |

### 구현 완료된 API 엔드포인트 전체 목록

| 엔드포인트 | 라우터 파일 | 테스트 파일 |
|---|---|---|
| `GET /api/overview` | `routers/overview.py` | `test_api_overview.py` |
| `GET /api/anomalies` | `routers/anomalies.py` | `test_api_anomalies.py` |
| `GET /api/forecast` | `routers/forecast.py` | `test_api_forecast.py` |
| `GET /api/budget`, `POST`, `PUT`, `DELETE` | `routers/budget.py` | `test_api_budget.py` |
| `GET /api/cost-explorer` | `routers/cost_explorer.py` | `test_api_cost_explorer.py` |
| `GET /api/recommendations` | `routers/recommendations.py` | `test_api_recommendations.py` |
| `GET /api/chargeback` | `routers/chargeback.py` | `test_api_chargeback.py` |
| `GET /api/settings`, `POST`, `PUT`, `DELETE` | `routers/settings.py` | `test_api_settings.py` |
| `GET /api/filters` | `routers/filters.py` | `test_api_filters.py` |
| `GET /api/ops/runs`, `/health`, `/live`, `/ready`, `/metrics` | `routers/ops.py` | `test_api_ops.py` |
| `GET /api/data-quality` | `routers/data_quality.py` | `test_data_quality.py` |
| `GET /api/export/{table}` | `routers/data_quality.py` | — |
| `GET /api/burn-rate` | `routers/burn_rate.py` | `test_burn_rate.py` |
| `GET /api/inventory` | `routers/inventory.py` | `test_resource_inventory.py` |
| `GET /api/tag-policy` | `routers/tag_policy.py` | `test_tag_policy.py` |
| `GET /api/cost-allocation/rules`, `POST`, `PUT`, `DELETE` | `routers/cost_allocation.py` | `test_cost_allocation.py` |
| `GET /api/cost-allocation` | `routers/cost_allocation.py` | `test_cost_allocation.py` |
| `GET /api/showback`, `/export` | `routers/showback.py` | `test_showback_report.py` |
| `GET /api/cost-trend`, `/compare` | `routers/cost_trend.py` | `test_cost_trend.py` |
| `GET /api/alerts`, `POST /api/alerts/{id}/acknowledge` | `routers/alerts.py` | `test_alert_history.py` |
| `GET /api/cloud-compare` | `routers/cloud_compare.py` | `test_cloud_compare.py` |
| `GET /api/savings` | `routers/savings.py` | `test_savings_tracker.py` |
| `GET /api/cost-heatmap` | `routers/cost_heatmap.py` | `test_api_cost_heatmap.py` |
| `GET /api/cost-risk` | `routers/cost_risk.py` | `test_cost_risk.py` |
| `GET /api/resources/{resource_id}` | `routers/resource_detail.py` | `test_resource_detail.py` |
| `GET /api/leaderboard` | `routers/leaderboard.py` | `test_leaderboard.py` |
| `GET /api/service-breakdown` | `routers/service_breakdown.py` | — |
| `GET /api/services/{service_name}` | `routers/service_detail.py` | `test_api_service_detail.py` |
| `GET /api/budget-forecast` | `routers/budget_forecast.py` | `test_budget_forecast.py` |
| `GET /api/env-breakdown` | `routers/env_breakdown.py` | `test_env_breakdown.py` |
| `GET /api/tag-compliance` | `routers/tag_compliance.py` | `test_tag_compliance.py` |
| `GET /api/anomaly-timeline` | `routers/anomaly_timeline.py` | `test_anomaly_timeline.py` |
| `GET /api/cloud-config`, `PUT` | `routers/cloud_config.py` | `test_api_cloud_config.py` |
| `GET /api/cloud-config/status` | `routers/cloud_config.py` | `test_api_cloud_config.py` |
| `GET /api/teams/{team}` | `routers/team_detail.py` | `test_api_team_detail.py` |
| `GET /api/environments/{env}` | `routers/env_detail.py` | `test_api_env_detail.py` |
| `GET /health` | `main.py` | — |

---

## 16. 미래 Phase 계획

> 아래 Phase는 구현 예정이다. 각 Phase는 독립적으로 완성 가능하며, 이전 Phase 위에 증분 확장된다.
> 구현 시 항상 API 라우터 → 프론트엔드 페이지 → pytest 테스트 순서로 진행한다.
> 매 Phase 완료 후: `uv run pytest tests/ -q` 전체 통과 확인 → CLAUDE.md 섹션 14에 히스토리 추가 → README.md Phase 표 업데이트.

### Phase 41 — Service Detail 드릴다운

**목표:** 서비스명 클릭 시 해당 서비스의 상세 분석 페이지로 이동

**API: `GET /api/services/{service_name}?months=6`**
- 404 반환 (서비스 미존재 시)
- `monthly_trend`: 최근 N개월 서비스별 비용 + 리소스 수
- `by_team`: 당월 팀별 비용 + pct (Top 10)
- `by_provider`: 당월 provider별 비용 + pct
- `by_env`: 당월 환경별 비용 + pct
- `top_resources`: 당월 리소스별 비용 Top-10
- `summary`: curr_cost, prev_cost, mom_change_pct, resource_count, team_count

**파일:**
- `api/routers/service_detail.py` — APIRouter, prefix `/api/services`
- `api/main.py` — `service_detail` 라우터 등록
- `api/routers/__init__.py` — `service_detail` 추가
- `web-app/app/(dashboard)/services/[service]/page.tsx` — Server Component
  - ← Services 뒤로 링크
  - KPI 카드 4개 (당월 비용, MoM%, 리소스 수, 팀 수)
  - 6개월 trend sparkline 바 차트
  - 팀별 TrendBar + Provider별 TrendBar
  - Top Resources 표 (resource_id → `/resources/{id}` 링크)
- `web-app/app/(dashboard)/services/page.tsx` — 서비스명에 `/services/{service}` 링크 추가
- `tests/test_api_service_detail.py` (10개) — shape/404/sorted/pct/months param 검증

**검증:** `601 + ~10 = ~611 tests pass`

---

### Phase 43 — 전역 검색 (`/search` + `/api/search`)

**목표:** 리소스 ID, 팀명, 서비스명으로 통합 검색

**API: `GET /api/search?q=<query>&limit=20`**
- `resources`: resource_id/resource_name 매칭 (cost_30d 포함)
- `teams`: team명 매칭 (curr_month_cost 포함)
- `services`: service_name 매칭 (cost_30d 포함)
- 각 카테고리 최대 5건, 전체 최대 15건

**파일:**
- `api/routers/search.py` — `GET /api/search`
  - PostgreSQL `ILIKE %s` 패턴 매칭
  - `fact_daily_cost` + `dim_resource_inventory` JOIN
- `web-app/app/(dashboard)/search/page.tsx` — Server Component
  - URL 파라미터 `?q=` 로 쿼리 수신
  - 리소스/팀/서비스 섹션별 결과 표시
  - 결과 항목 클릭 → 해당 드릴다운 페이지 이동
- `web-app/app/(dashboard)/Sidebar.tsx` — 검색 입력창 추가 (sidebar 상단, Enter → `/search?q=`)
- `tests/test_api_search.py` (8개) — shape/empty/case-insensitive/limit 검증

**구현 주의:**
- SQL 인젝션 방지: `%{query}%` 는 반드시 파라미터 바인딩으로 (`cur.execute("... ILIKE %s", [f"%{q}%"])`)
- 빈 쿼리(`q=""`)는 빈 결과 반환 (전체 목록 금지)

---

### Phase 44 — 알림 규칙 CRUD (`/alert-rules` + `/api/alert-rules`)

**목표:** 팀별·리소스별 커스텀 알림 임계값을 웹 UI에서 관리

**DB 테이블: `dim_alert_rules`**
```sql
CREATE TABLE IF NOT EXISTS dim_alert_rules (
    id          BIGSERIAL PRIMARY KEY,
    rule_name   VARCHAR NOT NULL,
    team        VARCHAR,           -- NULL = 전체 팀
    resource_id VARCHAR,           -- NULL = 전체 리소스
    metric      VARCHAR NOT NULL,  -- 'cost_spike', 'anomaly_count', 'budget_pct'
    threshold   DOUBLE PRECISION NOT NULL,
    severity    VARCHAR NOT NULL DEFAULT 'warning',  -- 'warning' | 'critical'
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

**API: `/api/alert-rules`**
- `GET /api/alert-rules` — 전체 규칙 목록 (team/enabled 필터)
- `POST /api/alert-rules` — 신규 규칙 (201, 규칙명 중복 409)
- `PUT /api/alert-rules/{id}` — 규칙 수정
- `DELETE /api/alert-rules/{id}` — 규칙 삭제 (204)

**파일:**
- `dagster_project/db_schema.py` — `dim_alert_rules` DDL 추가
- `api/routers/alert_rules.py` — 풀 CRUD
- `web-app/app/(dashboard)/alert-rules/AlertRulesClient.tsx` — Client Component
  - 규칙 표: rule_name / team / metric / threshold / severity / enabled / Edit+Delete
  - "Add Rule" 인라인 폼
  - enabled 토글 (PUT으로 즉시 반영)
- `web-app/app/(dashboard)/alert-rules/page.tsx` — Server Component 래퍼
- `Sidebar.tsx` — "Alert Rules" 항목 추가 (Alerts 근처)
- `tests/test_api_alert_rules.py` (10개) — CRUD 왕복, 409, 204 검증

---

### Phase 45 — 비용 이상치 Root Cause 분석 (`/api/anomaly-root-cause`)

**목표:** 특정 이상치 이벤트의 원인 추정 자동화

**API: `GET /api/anomaly-root-cause?resource_id=X&charge_date=YYYY-MM-DD`**
- 해당 resource_id의 당일 vs 직전 7일 평균 비용 비교
- 같은 서비스의 다른 리소스들 당일 비용 (peer comparison)
- 같은 팀의 당일 전체 비용 추이
- 가능한 원인 힌트: `cost_spike` / `new_resource` / `peer_spike` / `unknown`
- `confidence`: 0.0~1.0 신뢰도 점수

**파일:**
- `api/routers/anomaly_root_cause.py`
- `web-app/app/(dashboard)/anomalies/page.tsx` — 이상치 행 클릭 시 Root Cause 패널 인라인 표시
- `tests/test_api_anomaly_root_cause.py` (8개)

---

### Phase 46 — 비용 예측 정확도 대시보드 (`/forecast-accuracy`)

**목표:** Prophet 예측 vs 실제 비용 정확도를 월별로 추적

**Dagster Asset: `forecast_accuracy`**
- `dim_prophet_forecast`와 `fact_daily_cost` JOIN
- 월별 (team, service) 단위 MAE, RMSE, MAPE 계산
- `dim_forecast_accuracy` 테이블에 DELETE+INSERT 저장

**API: `GET /api/forecast-accuracy?months=6&team=X`**
- 월별 정확도 시계열
- 팀별 정확도 순위
- 전체 summary (avg_mape, best_team, worst_team)

**파일:**
- `dagster_project/assets/forecast_accuracy.py`
- `dagster_project/db_schema.py` — `dim_forecast_accuracy` DDL
- `api/routers/forecast_accuracy.py`
- `web-app/app/(dashboard)/forecast-accuracy/page.tsx` — Server Component
  - MAPE 컬러 코딩 (< 10% healthy, 10-25% warning, > 25% critical)
- `tests/test_forecast_accuracy.py` (8개)

---

### Phase 47 — 멀티 테넌트 권한 관리 기반 (읽기 전용)

**목표:** 팀별 데이터 가시성 제어 기반 마련 (인증 없이 팀 필터링만)

**DB 테이블: `dim_team_access`**
```sql
CREATE TABLE IF NOT EXISTS dim_team_access (
    viewer_team VARCHAR NOT NULL,
    target_team VARCHAR NOT NULL,
    PRIMARY KEY (viewer_team, target_team)
);
```

**API 변경:**
- `GET /api/overview?as_team=platform` — `platform` 팀 관점의 데이터만 반환
- 헤더 `X-As-Team` 지원 (미래 인증 레이어 연동 준비)

**파일:**
- `dagster_project/db_schema.py` — `dim_team_access` DDL
- `api/routers/team_access.py` — CRUD
- `web-app/app/(dashboard)/settings/page.tsx` — Team Access 섹션 추가
- `tests/test_team_access.py` (8개)

---

### Phase 48 — 대시보드 내보내기 (PDF/PNG 스크린샷)

**목표:** 주요 페이지를 PDF/PNG로 내보내는 기능

**방식:** Playwright headless browser 기반 스크린샷
- `POST /api/export/screenshot?page=/overview` — 해당 URL 스크린샷 → PNG bytes 반환
- Content-Disposition: attachment; filename="overview-2026-04.png"

**파일:**
- `api/routers/export_screenshot.py` — Playwright async API 사용
- `web-app/app/(dashboard)/layout.tsx` — "Export Page" 버튼 추가 (각 페이지 공통)
- `pyproject.toml` — `playwright>=1.40` 의존성 추가

**구현 주의:**
- Playwright는 `uv run playwright install chromium` 별도 설치 필요
- `@app.on_event("startup")`에서 browser 인스턴스 초기화
- 스크린샷 타임아웃 30초

---

### Phase 49 — 정기 이메일 리포트 (월별 Chargeback 이메일)

**목표:** 매월 초 팀별 비용 요약을 자동 이메일 발송

**Dagster Schedule: `monthly_email_report_schedule`**
- 매월 3일 09:00 UTC 실행
- `EmailSink`로 팀별 Chargeback + 이상치 요약 발송
- 발송 기록을 `dim_email_report_log`에 저장

**파일:**
- `dagster_project/assets/email_report.py` — `email_report` asset
- `dagster_project/db_schema.py` — `dim_email_report_log` DDL
- `dagster_project/schedules/monthly.py` — `monthly_email_report_schedule` 추가
- `tests/test_email_report.py` (6개) — 모킹 기반 (SMTP 실제 발송 없이)

---

### Phase 50 — 실제 클라우드 API 연동 기반

**목표:** 가상 데이터 생성기 대신 실제 클라우드 빌링 API 연동 옵션 제공

**AWS 연동 (`cloud.aws.enabled = true` 시):**
- `boto3` 기반 Cost Explorer API (`ce.get_cost_and_usage`)
- S3 CUR 파일 다운로드 옵션
- `AwsCurRealGenerator` — `CostSource` Protocol 구현체

**GCP 연동 (`cloud.gcp.enabled = true` 시):**
- `google-cloud-bigquery` 기반 Billing Export 쿼리
- `GcpBillingRealGenerator` — `CostSource` Protocol 구현체

**Azure 연동 (`cloud.azure.enabled = true` 시):**
- `azure-mgmt-costmanagement` 기반 Cost Management API
- `AzureCostRealGenerator` — `CostSource` Protocol 구현체

**파일:**
- `dagster_project/generators/aws_cur_real_generator.py`
- `dagster_project/generators/gcp_billing_real_generator.py`
- `dagster_project/generators/azure_cost_real_generator.py`
- `dagster_project/assets/raw_cur.py` — `cloud.aws.enabled` 설정에 따라 실제/가상 Generator 선택
- `pyproject.toml` — `boto3`, `google-cloud-bigquery`, `azure-mgmt-costmanagement` 선택적 의존성

**구현 주의:**
- 실제 Generator는 `try/except ImportError`로 선택적 임포트
- 가상 Generator는 항상 폴백으로 유지
- Cloud Config UI에서 키 설정 후 Dagster asset 재실행으로 연동

---

## 17. 개발 워크플로우 (Phase 진행 방법)

각 Phase 구현 시 반드시 아래 순서를 따른다:

```
1. API 라우터 작성 → api/routers/<domain>.py
   - APIRouter(prefix="/api/...", tags=[...])
   - PostgreSQL %s 파라미터 바인딩, f() 헬퍼로 float 변환
   - 404/409/204 HTTP 상태 코드 정확히 사용

2. api/main.py에 라우터 등록
   - import 추가
   - app.include_router() 추가

3. api/routers/__init__.py에 추가

4. 프론트엔드 페이지 작성
   - Server Component 기본, 인터랙션 있으면 Client Component 분리
   - export const dynamic = "force-dynamic" (SSR 페이지)
   - PageHeader / Card / CardHeader / MetricCard / SeverityBadge 컴포넌트 사용
   - CSS 토큰: var(--text-primary), var(--text-secondary), var(--text-tertiary)
   - 테이블 헤더 패딩: 첫 컬럼 "0 8px 12px 0", 중간 "0 8px 12px 8px", 마지막 "0 0 12px 8px"
   - 금액: formatCurrency() 함수 사용

5. Sidebar.tsx에 NAV 항목 추가

6. lib/types.ts에 타입 추가 (필요시)

7. lib/api.ts에 API 메서드 추가 (필요시)

8. pytest 테스트 작성 → tests/test_api_<domain>.py
   - @pytest.fixture(scope="module") def client() → TestClient(app)
   - 200/404/409/204 상태 코드 검증
   - 응답 shape 검증 (필수 필드 존재 여부)
   - CRUD 왕복 테스트 (create → read → update → delete)
   - 테스트 데이터 cleanup (unique prefix + DELETE)

9. 검증
   cd web-app && npx next build    # TypeScript 에러 없어야 함
   uv run pytest tests/ -q         # 전체 통과

10. CLAUDE.md 섹션 14에 Phase 히스토리 추가
    - Phase N — 제목
    - 구현 내용 bullet points
    - **XXX tests pass** ✅

11. README.md Phase 표에 행 추가
```

### 공통 구현 패턴 레퍼런스

**API 라우터 기본 구조:**
```python
"""GET /api/<domain> — 설명."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Query
from ..deps import db_read, f

router = APIRouter(prefix="/api/<domain>", tags=["<domain>"])

@router.get("")
def get_data(
    billing_month: str | None = Query(None),
) -> dict[str, Any]:
    with db_read() as conn:
        with conn.cursor() as cur:
            # latest month 자동 감지
            if billing_month:
                month = billing_month
            else:
                cur.execute("SELECT to_char(MAX(charge_date),'YYYY-MM') FROM fact_daily_cost")
                row = cur.fetchone()
                month = row[0] if row and row[0] else "2024-01"
            # 쿼리
            cur.execute("SELECT ... FROM ... WHERE ... = %s", (month,))
            rows = cur.fetchall()
    return {"billing_month": month, "items": [...]}
```

**드릴다운 페이지 404 패턴:**
```python
cur.execute("SELECT COUNT(*) FROM fact_daily_cost WHERE <entity> = %s", (name,))
row = cur.fetchone()
if not row or row[0] == 0:
    raise HTTPException(status_code=404, detail=f"<Entity> '{name}' not found")
```

**Next.js 동적 라우트 페이지 기본 구조:**
```typescript
export const dynamic = "force-dynamic";

export default async function DetailPage({ params }: { params: { id: string } }) {
  const name = decodeURIComponent(params.id);
  let data: DetailData;
  try {
    const res = await fetch(`${API_BASE}/api/<domain>/${encodeURIComponent(name)}`, { cache: "no-store" });
    if (!res.ok) {
      if (res.status === 404) throw new Error(`"${name}" not found`);
      throw new Error(`API ${res.status}`);
    }
    data = await res.json();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }
  return (
    <div style={{ maxWidth: "1200px" }}>
      <div style={{ marginBottom: "8px" }}>
        <Link href="/<parent>" style={{ fontSize: "12px", color: "var(--text-tertiary)", textDecoration: "none" }}>
          ← <Parent>
        </Link>
      </div>
      <PageHeader title={name} description="..." />
      {/* KPI 카드 */}
      {/* 콘텐츠 */}
    </div>
  );
}
```

**테스트 기본 구조:**
```python
"""Tests for /api/<domain> endpoint."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from api.main import app

@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)

def test_<domain>_returns_200(client: TestClient) -> None:
    r = client.get("/api/<domain>")
    assert r.status_code == 200

def test_<domain>_shape(client: TestClient) -> None:
    body = client.get("/api/<domain>").json()
    assert "billing_month" in body
    assert "items" in body
    assert isinstance(body["items"], list)
```
```