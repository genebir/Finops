# FinOps Platform

로컬 환경에서 돌아가는 **멀티 클라우드 FinOps 플랫폼**. AWS · GCP · Azure 가상 빌링 데이터를 Medallion 아키텍처로 처리하고, 이상치 탐지 · 비용 예측 · 예산 관리 · Chargeback을 제공한다.

## 핵심 질문

1. **"지금 가장 많은 비용을 발생시키는 게 뭐야?"** — Top-N 비용 드라이버 (서비스·리소스·팀·태그별, AWS+GCP+Azure 통합)
2. **"이상하게 튄 비용이 있어?"** — Z-score · IsolationForest · MovingAverage 멀티 탐지기
3. **"예측이랑 실제가 얼마나 달라?"** — Infracost(Terraform) + Prophet(시계열) Variance 분석
4. **"예산 대비 현황은?"** — 팀/환경별 예산 관리, 초과 알림, Chargeback 리포트
5. **"전체 현황을 한눈에 보고 싶다"** — Next.js 모니터링 대시보드 (30개 페이지, i18n EN/KO) + Streamlit 내부 디버깅용

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
| Analytics | PostgreSQL ≥14 | Silver→Gold 집계, 분석 마트, 런타임 설정 |
| Validation | Pydantic v2 | 스키마·값 검증 |
| Config | PyYAML + Pydantic | 정적 설정 로딩 |
| Cost Forecast | Infracost CLI | Terraform 기반 비용 예측 |
| ML Forecast | Prophet ≥1.1 | 시계열 기반 비용 예측 |
| ML Anomaly | scikit-learn ≥1.4, statsmodels ≥0.14 | IsolationForest / ARIMA 이상치 탐지 |
| Alerting | slack-sdk ≥3.0 / smtplib | Slack Webhook + 이메일 알림 |
| CLI Dashboard | Rich ≥13.0 | 터미널 대시보드 |
| Web Dashboard | Streamlit ≥1.35 + Plotly ≥5.0 | 웹 대시보드 (내부 디버깅용) |
| Monitoring UI | Next.js 14 + Tailwind | 모니터링 대시보드 (30페이지) |
| API Server | FastAPI | REST API (35+ 엔드포인트) |
| Standard | FOCUS 1.0 | 비용 데이터 규격 |
| Language | Python 3.14+ | |
| Package Mgmt | uv | |
| Lint/Type | ruff + mypy (strict) | |

## 빠른 시작 (신규 머신)

```bash
# 원커맨드 설치 (macOS/Linux/WSL)
bash install.sh

# 선택: Infracost CLI 포함
bash install.sh --with-infracost
```

## 실행 방법

```bash
# 의존성 설치
uv sync

# 환경 설정
cp .env.example .env

# 원커맨드 개발환경 셋업 (테이블 + 시드 + asset 실행 + 뷰)
uv run python scripts/setup.py --all
# 이미 완료된 단계는 자동 스킵, 언제든 재실행 가능

# 개별 단계 실행도 가능:
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

## 환경변수

| 변수 | 용도 | 기본값 |
|---|---|---|
| `SLACK_WEBHOOK_URL` | Slack 알림 Webhook URL | (미설정 시 비활성) |
| `ALERT_EMAIL_TO` | 이메일 알림 수신 주소 (쉼표 구분) | (미설정 시 비활성) |
| `SMTP_HOST` / `SMTP_PORT` | SMTP 서버 | localhost / 587 |
| `SMTP_USER` / `SMTP_PASSWORD` | SMTP 인증 | |
| `CUR_SEED` | AWS CUR 생성 시드 | 42 |
| `POSTGRES_HOST` / `POSTGRES_PORT` | PostgreSQL 접속 | localhost / 5432 |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | PostgreSQL 인증 | finops_app / finops_secret_2026 |
| `POSTGRES_DBNAME` | PostgreSQL DB 이름 | finops |
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
│   ├── resources/              # Dagster Resource 래퍼 (DuckDB→PostgreSQL, Iceberg, Budget 등)
│   ├── schemas/                # FOCUS 1.0 Pydantic 스키마
│   ├── sinks/                  # ConsoleSink, SlackSink, EmailSink
│   └── utils/                  # flatten_tags 등 공유 유틸
├── api/                        # FastAPI 백엔드 (35+ 엔드포인트)
│   ├── main.py                 # 앱 엔트리 (CORS, 라우터 등록)
│   ├── deps.py                 # db_read/db_write (psycopg2)
│   ├── models/                 # Pydantic 요청/응답 모델
│   └── routers/                # 도메인별 API 라우터 (30+개)
├── web-app/                    # Next.js 14 모니터링 대시보드 (30페이지, i18n EN/KO)
│   ├── app/(dashboard)/        # 페이지 (overview, anomalies, budget, ...)
│   ├── components/             # Card, MetricCard, Sidebar, PageHeader
│   └── lib/                    # API 클라이언트, i18n, 타입 정의
├── scripts/
│   ├── setup.py                # 멱등 개발환경 셋업 (--all로 전체 부트스트랩)
│   ├── init_db.py              # DB 스키마 부트스트랩 CLI
│   ├── dashboard.py            # Rich CLI 대시보드
│   └── streamlit_app.py        # Streamlit 웹 대시보드 (내부 디버깅용)
├── sql/marts/                  # PostgreSQL DDL / View SQL
├── terraform/sample/           # Infracost 분석 대상 IaC (EC2/RDS/S3)
├── tests/                      # pytest 테스트 (631개)
├── install.sh                  # 크로스플랫폼 원커맨드 인스톨러
└── data/                       # 생성된 데이터 (gitignored)
    ├── warehouse/              # Iceberg 데이터
    ├── catalog.db              # SqlCatalog SQLite
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
| Phase 8 | 디자인 시스템, Streamlit 개선 | **311 / 94.6%** |
| Phase 8.1 | FastAPI + Next.js 14 대시보드 MVP (Overview) | **311 / 94.6%** |
| Phase 9 | 대시보드 5개 페이지 확장 (anomalies/budget/explorer/forecast/recommendations) | **311 / 94.6%** |
| Phase 10 | API 재구조화 (router/model/deps), Budget CRUD, Settings CRUD UI | **311 / 94.6%** |
| Phase 11 | DuckDB → PostgreSQL 전면 마이그레이션 | **288 / pass** |
| Phase 11.1 | Settings 풀 CRUD, 테이블 UX 개선 | **288 / pass** |
| Phase 12 | 옵스 관측성 (pipeline_run_log, /api/ops/*, Prometheus metrics, Ops 대시보드) | **299 / pass** |
| Phase 13 | 데이터 품질 검증 asset + CSV export API + Data Quality 대시보드 | **309 / pass** |
| Phase 14 | 번 레이트 asset + Dagster 스케줄 + /api/burn-rate + Burn Rate 대시보드 | **317 / pass** |
| Phase 15 | 리소스 인벤토리 + 태그 완성도 검증 + /api/inventory | **327 / pass** |
| Phase 16 | 태그 정책 엔진 + dim_tag_violations + /api/tag-policy | **340 / pass** |
| Phase 17 | 비용 배분 + 분할 규칙 CRUD + /api/cost-allocation | **351 / pass** |
| Phase 18 | Showback 리포트 asset + JSON export + /api/showback | **360 / pass** |
| Phase 19 | 비용 트렌드 분석 + 기간 비교 + /api/cost-trend + /compare | **371 / pass** |
| Phase 20 | 알림 히스토리 영속화 + Acknowledge 워크플로우 + /api/alerts | **384 / pass** |
| Phase 21 | Alerts 대시보드 페이지 (severity 필터, Ack 워크플로우 UI) | **384 / pass** |
| Phase 22 | 멀티클라우드 비교 API + Cloud Compare 대시보드 (provider × team 매트릭스) | **395 / pass** |
| Phase 23 | 절감 실적 추적 asset + dim_savings_realized + /api/savings | **405 / pass** |
| Phase 24 | Savings 대시보드 페이지 + /api/cost-heatmap (daily cost matrix) | **415 / pass** |
| Phase 25 | 비용-리스크 상관 API /api/cost-risk (cost × anomaly_count risk score) | **425 / pass** |
| Phase 26 | Risk 대시보드 + 리소스 드릴다운 API /api/resources/{id} | **434 / pass** |
| Phase 27 | 팀 리더보드 /api/leaderboard + 서비스 카테고리 /api/service-breakdown | **449 / pass** |
| Phase 28 | Leaderboard + Services 대시보드 페이지 (MoM badge, PctBar, 메달) | **449 / pass** |
| Phase 29 | 예산 예측 asset + dim_budget_forecast + /api/budget-forecast | **459 / pass** |
| Phase 30 | Budget Forecast 대시보드 + /api/env-breakdown (환경별 교차표) | **468 / pass** |
| Phase 31 | Env Breakdown 대시보드 + 태그 준수율 점수 asset + /api/tag-compliance + Tag Compliance 대시보드 | **477 / pass** |
| Phase 32 | Anomaly Timeline API/대시보드 + Cloud Config API/UI + 디자인 통일 + 사이드바 카테고리 그룹 | **498 / pass** |
| Phase 33 | Inventory / Showback / Tag Policy 대시보드 페이지 + Burn Rate 디자인 수정 | **498 / pass** |
| Phase 34 | Cost Trend 대시보드 페이지 (월별 바 + 상세 표 + 기간 비교 섹션) | **498 / pass** |
| Phase 35 | Resource Detail 드릴다운 페이지 `/resources/[id]` + Inventory 링크 연결 | **498 / pass** |
| Phase 36 | Cost Allocation 대시보드 (rules CRUD + allocated cost 조회) | **498 / pass** |
| Phase 37 | API 엔드포인트 테스트 72개 추가 (7개 파일) — API 커버리지 92% | **570 / pass** |
| Phase 38 | Overview 페이지 강화 (provider breakdown + 6개월 trend sparkline + resource 드릴다운 링크) | **570 / pass** |
| Phase 39 | Cost Heatmap 대시보드 + Cloud Config 대시보드 (provider 연결 설정 인라인 편집 UI) | **591 / pass** |
| Phase 40 | Team Detail API `/api/teams/{team}` + 드릴다운 페이지 + Leaderboard 링크 | **601 / pass** |
| Phase 40.1 | 프로덕션 준비 (i18n 완성, 메타데이터, 레이아웃 표준화) + `scripts/setup.py` 멱등 셋업 | **631 / pass** |
