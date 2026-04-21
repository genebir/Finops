# FinOps Platform

로컬 환경에서 돌아가는 **멀티 클라우드 FinOps 플랫폼**. AWS · GCP · Azure 가상 빌링 데이터를 Medallion 아키텍처로 처리하고, 이상치 탐지 · 비용 예측 · 예산 관리 · Chargeback을 제공한다.

## 핵심 질문

1. **"지금 가장 많은 비용을 발생시키는 게 뭐야?"** — Top-N 비용 드라이버 (서비스·리소스·팀·태그별, AWS+GCP+Azure 통합)
2. **"이상하게 튄 비용이 있어?"** — Z-score · IsolationForest · MovingAverage 멀티 탐지기
3. **"예측이랑 실제가 얼마나 달라?"** — Infracost(Terraform) + Prophet(시계열) Variance 분석
4. **"예산 대비 현황은?"** — 팀/환경별 예산 관리, 초과 알림, Chargeback 리포트
5. **"전체 현황을 한눈에 보고 싶다"** — Streamlit 웹 대시보드 (6개 탭)

## 아키텍처

```
AWS 파이프라인      GCP 파이프라인      Azure 파이프라인
[raw_cur]          [raw_cur_gcp]      [raw_cur_azure]
     │                   │                   │
     ▼                   ▼                   ▼
[bronze_iceberg]  [bronze_iceberg_gcp] [bronze_iceberg_azure]
     │                   │                   │
     ▼                   ▼                   ▼
[silver_focus]    [silver_focus_gcp]  [silver_focus_azure]
     └───────────────────┴───────────────────┘
                         │
                  fact_daily_cost  ← provider 컬럼으로 3개 클라우드 통합
                         │
     ┌───────────────────┼─────────────────────────┐
     ▼                   ▼                         ▼
[anomaly_detection] [prophet_forecast]       [budget_alerts]
ZScore+IF+MA         신뢰구간 예측            팀/환경별 예산
     │                   │                         │
     ▼                   ▼                         ▼
[alert_dispatch] [forecast_variance_prophet]  [chargeback]
     │                                       dim_chargeback
     └─────────────── data/reports/*.csv ──────────┘

[infracost_forecast] → [variance]
[fx_rates] → dim_fx_rates
scripts/dashboard.py     (Rich CLI 대시보드)
scripts/streamlit_app.py (Streamlit 웹 대시보드)
```

## 기술 스택

| 레이어 | 도구 | 역할 |
|---|---|---|
| Orchestrator | Dagster ≥1.8 | Asset 기반 파이프라인 관리 |
| 전처리 | Polars ≥1.0 | Bronze→Silver 정제 |
| Table Format | Apache Iceberg (PyIceberg) | 로컬 레이크하우스 |
| Catalog | SqlCatalog (SQLite) | 로컬 Iceberg 메타스토어 |
| Analytics | DuckDB ≥1.0 | Silver→Gold 집계, 분석 마트 |
| Validation | Pydantic v2 | 스키마·값 검증 |
| Config | PyYAML + Pydantic | 정적 설정 로딩 |
| Cost Forecast | Infracost CLI | Terraform 기반 비용 예측 |
| ML Forecast | Prophet ≥1.1 | 시계열 기반 비용 예측 |
| ML Anomaly | scikit-learn ≥1.4, statsmodels ≥0.14 | IsolationForest / ARIMA 이상치 탐지 |
| Alerting | slack-sdk ≥3.0 / smtplib | Slack Webhook + 이메일 알림 |
| CLI Dashboard | Rich ≥13.0 | 터미널 대시보드 |
| Web Dashboard | Streamlit ≥1.35 + Plotly ≥5.0 | 웹 대시보드 |
| Standard | FOCUS 1.0 | 비용 데이터 규격 |
| Language | Python 3.14+ | |
| Package Mgmt | uv | |
| Lint/Type | ruff + mypy (strict) | |

## 실행 방법

```bash
# 의존성 설치
uv sync

# 환경 설정
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

## 환경변수

| 변수 | 용도 | 기본값 |
|---|---|---|
| `SLACK_WEBHOOK_URL` | Slack 알림 Webhook URL | (미설정 시 비활성) |
| `ALERT_EMAIL_TO` | 이메일 알림 수신 주소 (쉼표 구분) | (미설정 시 비활성) |
| `SMTP_HOST` / `SMTP_PORT` | SMTP 서버 | localhost / 587 |
| `SMTP_USER` / `SMTP_PASSWORD` | SMTP 인증 | |
| `CUR_SEED` | AWS CUR 생성 시드 | 42 |
| `DUCKDB_PATH` | DuckDB 파일 경로 | data/marts.duckdb |
| `ICEBERG_WAREHOUSE` | Iceberg 웨어하우스 경로 | data/warehouse |

## 런타임 설정 변경 (재시작 불필요)

```sql
-- 이상치 탐지 임계값 조정
UPDATE platform_settings SET value = '3.0' WHERE key = 'anomaly.zscore.warning';

-- 활성 탐지기 변경 (zscore, isolation_forest, moving_average, arima)
UPDATE platform_settings SET value = 'zscore,moving_average,arima' WHERE key = 'anomaly.active_detectors';

-- 예산 경고 임계값 조정
UPDATE platform_settings SET value = '70.0' WHERE key = 'budget.alert_threshold_pct';
```

## 디렉토리 구조

```
finops-platform/
├── config/
│   ├── settings.yaml           # 정적 설정 (버전 관리)
│   └── settings.local.yaml     # 로컬 재정의 (gitignore)
├── dagster_project/
│   ├── assets/                 # Dagster asset 정의 (22개)
│   ├── core/                   # Protocol 추상화 (CostSource, AnomalyDetector, FxProvider 등)
│   ├── detectors/              # ZScore, IsolationForest, MovingAverage
│   ├── generators/             # 가상 AWS/GCP/Azure CUR 생성기
│   ├── providers/              # ProphetProvider, StaticFxProvider
│   ├── resources/              # Dagster Resource 래퍼 (DuckDB, Iceberg, Budget 등)
│   ├── schemas/                # FOCUS 1.0 Pydantic 스키마
│   ├── sinks/                  # ConsoleSink, SlackSink, EmailSink
│   └── utils/                  # flatten_tags 등 공유 유틸
├── scripts/
│   ├── dashboard.py            # Rich CLI 대시보드
│   └── streamlit_app.py        # Streamlit 웹 대시보드 (6탭)
├── sql/marts/                  # DuckDB DDL / View SQL
├── terraform/sample/           # Infracost 분석 대상 IaC (EC2/RDS/S3)
├── tests/                      # pytest 테스트 (272개, 95.71% 커버리지)
└── data/                       # 생성된 데이터 (gitignored)
    ├── warehouse/              # Iceberg 데이터
    ├── catalog.db              # SqlCatalog SQLite
    ├── marts.duckdb            # DuckDB
    └── reports/                # 출력 CSV
```

## Phase 히스토리

| Phase | 주요 내용 | 테스트 |
|---|---|---|
| Phase 1 | AWS CUR → Medallion(Bronze/Silver/Gold) + Infracost Variance | - |
| Phase 2 | Z-score 이상치 탐지, ConsoleSink/SlackSink, Prophet 예측 | - |
| Phase 3 | GCP 파이프라인, IsolationForest, Prophet 신뢰구간, Rich 대시보드 | - |
| Phase 4 | Azure 파이프라인, BudgetStore, Chargeback, Streamlit 대시보드 | 200 / 70.2% |
| Phase 5 | FX 환율, MovingAverage 탐지기, EmailSink, 통합 테스트 | **272 / 95.7%** |
| Phase 6 | ARIMA 탐지기, HTTP FX Provider, Prophet CV, Budget CRUD UI | **298 / 94.9%** |
| Phase 7 | Autoencoder 탐지기, 비용 추천 엔진, Settings UI | **311 / 94.6%** |
