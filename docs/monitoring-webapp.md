# FinOps Platform — Monitoring Web Application

> 기존 Streamlit 대시보드(`scripts/streamlit_app.py`)를 대체할 **프로덕션급 모니터링 웹 애플리케이션** 사양서.
> 이 문서는 Claude Code가 웹 앱을 처음부터 동일하게 재현하는 데 필요한 모든 컨텍스트를 담는다.
>
> **작업 시작 전 반드시 함께 읽을 문서:**
> - `CLAUDE.md` — 프로젝트 전체 사양 (데이터 모델, 도메인, 파이프라인)
> - `docs/design-system.md` — 디자인 토큰·타이포·색상·shape language
>
> 이 문서는 **어떤 화면을 어떻게 구성할지**에 집중한다. 디자인 토큰은 반복 정의하지 않는다.

---

## 1. 프로젝트 목표

### 1.1 왜 Streamlit을 버리는가

- **디자인 완성도 한계** — Streamlit은 커스텀 CSS로도 Arc 수준의 완성도를 낼 수 없다. 사이드바 애니메이션, 페이지 전환, 인터랙티브 폼 컴포넌트 모두 제약이 크다.
- **실시간성 부재** — Streamlit은 매 interaction마다 전체 스크립트를 재실행한다. 모니터링 UI에 필수적인 polling·WebSocket·점진적 업데이트가 부자연스럽다.
- **라우팅·상태 관리 한계** — 깊은 drill-down, URL 공유, 북마크, 다중 탭 플로우가 어렵다.
- **오픈소스 쇼케이스로 부적합** — 스크린샷 품질이 제품 평가를 좌우하는데, Streamlit 특유의 "대시보드 냄새"가 남는다.

### 1.2 새 웹 앱의 목표

1. **프로덕션급 모니터링 UX** — Datadog, Grafana, Linear 수준의 인터랙션 품질
2. **실시간성** — 파이프라인 상태·비용 변화·알림을 실시간 반영
3. **URL 기반 상태** — 모든 필터·drill-down이 URL에 반영되어 공유·북마크 가능
4. **오픈소스 쇼케이스** — 스크린샷·데모 영상이 그대로 랜딩페이지 콘텐츠
5. **기존 Gold 마트 재사용** — DuckDB 기반 `fact_daily_cost`, `dim_*`, `v_*` 테이블을 그대로 쿼리

### 1.3 Streamlit과의 공존

`scripts/streamlit_app.py`는 **내부 운영용·빠른 디버깅용**으로 유지한다.
새 웹 앱(`web-app/`)은 **외부 공개·모니터링·쇼케이스용**이다. 두 UI는 동일한 DuckDB를 읽으며 충돌하지 않는다.

---

## 2. 기술 스택

| 레이어 | 도구 | 버전 | 역할 |
|---|---|---|---|
| Framework | Next.js (App Router) | ≥15 | 풀스택 React, SSR·SSG·API Routes |
| Language | TypeScript | ≥5.4 | strict mode |
| Styling | Tailwind CSS | ≥3.4 | `docs/design-system.md` 토큰 매핑 |
| UI Primitives | Radix UI | latest | 접근성 보장 headless 컴포넌트 |
| Charts | Recharts + D3 | ≥2.12 / ≥7 | FinOps 차트, treemap은 D3 |
| Icons | Phosphor Icons React | ≥2.0 | duotone 아이콘 (이모지 금지) |
| Data Fetching | TanStack Query | ≥5.0 | 캐싱·polling·mutation |
| State | Zustand + nuqs | ≥4.0 / ≥2.0 | 클라이언트 상태 + URL 상태 |
| Backend API | FastAPI | ≥0.110 | DuckDB 쿼리 래핑, `/api/*` 제공 |
| DB Driver | duckdb (Python) | ≥1.0 | 기존 `data/marts.duckdb` 읽기 |
| Validation | Pydantic v2 / Zod | ≥2.0 / ≥3.22 | 백엔드/프런트 스키마 검증 |
| Testing | Vitest + Playwright | latest | 단위 + E2E |
| Deployment | Docker Compose | — | Next.js + FastAPI + DuckDB 읽기 전용 마운트 |

### 2.1 왜 Next.js + FastAPI 분리인가

- **DuckDB 파이썬 바인딩이 가장 성숙** — Node.js `duckdb` 드라이버도 있지만 Python이 훨씬 안정적이고 이 프로젝트의 모든 파이프라인이 Python이다.
- **기존 Protocol·Provider 재사용** — `FxProvider`, `AnomalyDetector` 등을 API 레이어에서 그대로 쓸 수 있다.
- **풀 Node.js 스택 대비 타입 안정성** — FastAPI는 Pydantic, Next.js는 Zod로 스키마를 공유 가능 (OpenAPI 스펙 자동 생성).
- **배포 단순함** — Docker Compose 한 파일에 두 서비스 묶음.

### 2.2 대안 검토 및 기각 이유

- **SvelteKit / Remix** — 생태계·오픈소스 가시성 면에서 Next.js 우위.
- **단일 Next.js + duckdb-node** — 드라이버 불안정, 기존 Python 자산 재사용 불가.
- **Django + HTMX** — 모니터링 UI의 인터랙티브성(실시간 차트, drill-down)에 부적합.
- **Grafana 플러그인** — 이 프로젝트의 FinOps 도메인 특화 UI(cost_unit drill-down, variance 분석)를 표현하기 어려움.

---

## 3. 디렉토리 구조

기존 프로젝트에 `web-app/`과 `api/`를 추가한다.

```
finops-platform/
├── CLAUDE.md
├── docs/
│   ├── design-system.md
│   └── monitoring-webapp.md         # 이 문서
├── dagster_project/                  # 기존 그대로
├── scripts/
│   └── streamlit_app.py              # 기존 유지 (내부용)
├── api/                              # [신규] FastAPI 백엔드
│   ├── pyproject.toml
│   ├── main.py                       # FastAPI 앱 엔트리
│   ├── config.py                     # 기존 config 재사용 import
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── overview.py               # GET /api/overview
│   │   ├── costs.py                  # GET /api/costs/*
│   │   ├── anomalies.py              # GET /api/anomalies
│   │   ├── forecast.py               # GET /api/forecast
│   │   ├── budget.py                 # GET/POST/PATCH/DELETE /api/budget
│   │   ├── chargeback.py             # GET /api/chargeback
│   │   ├── recommendations.py        # GET /api/recommendations
│   │   ├── settings.py               # GET/PATCH /api/settings
│   │   ├── fx.py                     # GET /api/fx
│   │   └── pipeline.py               # GET /api/pipeline/status (Dagster 연동)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── cost.py
│   │   ├── anomaly.py
│   │   ├── budget.py
│   │   └── ...                       # Pydantic 응답 스키마
│   ├── services/
│   │   ├── __init__.py
│   │   ├── duckdb_client.py          # 기존 DuckDBResource 로직 재사용
│   │   ├── settings_service.py       # SettingsStoreResource 래핑
│   │   ├── budget_service.py         # BudgetStoreResource 래핑
│   │   └── dagster_client.py         # Dagster GraphQL 호출 (선택)
│   ├── middleware/
│   │   └── cors.py
│   └── tests/
│       └── ...
├── web-app/                          # [신규] Next.js 프런트엔드
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.mjs
│   ├── tailwind.config.ts            # design-system.md 토큰 매핑
│   ├── postcss.config.mjs
│   ├── app/
│   │   ├── layout.tsx                # 글로벌 폰트·스타일
│   │   ├── globals.css               # CSS 변수 정의 (design-system.md 그대로)
│   │   ├── page.tsx                  # / → /overview 리다이렉트
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx            # 사이드바 + 메인 레이아웃
│   │   │   ├── overview/page.tsx
│   │   │   ├── costs/
│   │   │   │   ├── page.tsx          # 비용 익스플로러
│   │   │   │   └── [resourceId]/page.tsx  # 리소스 상세 drill-down
│   │   │   ├── anomalies/page.tsx
│   │   │   ├── forecast/page.tsx
│   │   │   ├── budget/page.tsx
│   │   │   ├── chargeback/page.tsx
│   │   │   ├── recommendations/page.tsx
│   │   │   └── settings/page.tsx
│   │   └── api/                      # (선택) Next 내부 API, 주로 proxy 용도
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx           # Arc 스타일 좌측 네비
│   │   │   ├── TopBar.tsx            # 월 선택, 통화 선택, 검색
│   │   │   └── PageHeader.tsx
│   │   ├── cards/
│   │   │   ├── MetricCard.tsx        # KPI 카드
│   │   │   ├── TrendCard.tsx         # 미니 차트 포함 카드
│   │   │   └── BudgetGaugeCard.tsx
│   │   ├── charts/
│   │   │   ├── StackedAreaChart.tsx  # Multi-cloud stacked area
│   │   │   ├── AnomalyScatter.tsx
│   │   │   ├── VarianceBar.tsx
│   │   │   ├── ChargebackTreemap.tsx
│   │   │   └── ForecastBand.tsx      # Prophet 신뢰구간 차트
│   │   ├── tables/
│   │   │   ├── DataTable.tsx         # 범용 테이블 (정렬·필터·페이징)
│   │   │   ├── TopResourcesTable.tsx
│   │   │   └── AnomalyTable.tsx
│   │   ├── filters/
│   │   │   ├── MonthPicker.tsx
│   │   │   ├── ProviderFilter.tsx    # AWS/GCP/Azure 토글
│   │   │   ├── CostUnitFilter.tsx    # team:product:env 계층 필터
│   │   │   └── CurrencySelector.tsx  # FX 적용
│   │   ├── status/
│   │   │   ├── SeverityBadge.tsx     # critical/warning/healthy pill
│   │   │   ├── ProviderBadge.tsx
│   │   │   └── TrendIndicator.tsx    # ▲ ▼ 증감
│   │   └── primitives/
│   │       ├── Button.tsx
│   │       ├── Card.tsx
│   │       ├── Dialog.tsx
│   │       └── ...                   # Radix 기반
│   ├── lib/
│   │   ├── api-client.ts             # fetch 래퍼, TanStack Query hooks
│   │   ├── formatters.ts             # 금액·퍼센트·날짜 포매터
│   │   ├── constants.ts              # enum, 고정값
│   │   ├── url-state.ts              # nuqs 기반 URL 상태
│   │   └── types.ts                  # API 응답 타입 (Zod 스키마)
│   ├── hooks/
│   │   ├── useCosts.ts
│   │   ├── useAnomalies.ts
│   │   ├── useBudget.ts
│   │   └── ...
│   └── public/
│       └── icons/
├── docker-compose.yml                # [신규] api + web-app
└── data/                             # 기존 그대로 (읽기 전용 마운트)
```

---

## 4. 페이지 구성

각 페이지는 URL로 직접 접근 가능하며, 주요 상태는 query string에 반영한다.

### 4.1 `/overview` — 전체 현황 대시보드

**목적:** "전체 현황을 한눈에" (CLAUDE.md 섹션 1의 5번 질문)

**레이아웃:** 12컬럼 그리드, 상단 KPI 4개 + 중앙 메인 차트 + 하단 요약 카드 3개

**구성 요소:**
- **상단 KPI 카드 4개** (2x2 또는 1x4)
  - 이번 달 총 비용 (MTD, 전월 동기 대비)
  - 이번 달 예상 총액 (Prophet forecast)
  - 활성 이상치 수 (critical + warning)
  - 예산 초과 팀 수
- **메인 차트: Multi-Cloud Stacked Area** (30일 lookback)
  - provider별 stack, 범례는 pill 토글 (`AWS` `GCP` `Azure`)
  - hover 시 일자별 총합 + provider별 breakdown
- **Top 5 Cost Drivers** — `v_top_resources_30d` 상위 5개, 카드 형태
- **Recent Anomalies** — 최근 7일 critical/warning 이상치 타임라인
- **Budget at Risk** — `over` + `warning` 상태 예산 목록, 사용률 순

**URL 파라미터:** `?month=2024-01&currency=USD&providers=aws,gcp,azure`

### 4.2 `/costs` — 비용 익스플로러

**목적:** "지금 가장 많은 비용을 발생시키는 게 뭐야?" (질문 1)

**레이아웃:** 좌측 필터 패널(고정 280px) + 우측 메인 콘텐츠

**구성 요소:**
- **필터 패널**
  - Provider (AWS/GCP/Azure 체크박스)
  - Cost Unit (team → product → env 계층 트리)
  - Service (AWS EC2, GCP Compute Engine, Azure VM 등)
  - Region
  - 날짜 범위 (월 단위 또는 커스텀)
- **상단 요약 바** — 선택된 필터 하의 총 비용·변화율
- **메인 시각화 탭 전환**
  - Treemap: service → resource 계층
  - Bar: Top N resources (제한 select)
  - Line: 시계열 (필터 조합별)
- **상세 테이블** — 하단 `DataTable`, 컬럼 정렬·페이징·CSV export
  - 각 행 클릭 시 `/costs/[resourceId]`로 drill-down

**URL 파라미터:** `?providers=aws&teams=platform&services=ec2&view=treemap`

### 4.3 `/costs/[resourceId]` — 리소스 상세

**구성 요소:**
- 상단 리소스 메타데이터 (provider, service, region, tags)
- 60일 비용 시계열 (Prophet forecast band 오버레이)
- 해당 리소스의 이상치 이력
- Variance (예측 vs 실제)
- 관련 추천 (있을 경우)

### 4.4 `/anomalies` — 이상치 탐지 센터

**목적:** "이상하게 튄 비용이 있어?" (질문 2)

**구성 요소:**
- **상단 Severity Summary** — critical / warning / normal 카운트
- **Detector Filter Chips** — zscore / isolation_forest / moving_average / arima / autoencoder 토글
- **메인 차트: Anomaly Scatter**
  - x축 날짜, y축 비용, 점 크기·색상으로 severity 표현
  - 클릭 시 오른쪽 side panel에 상세 표시
- **Anomaly Table** — 정렬·필터 가능, 컬럼: 일자, 리소스, cost_unit, severity, z-score, detector, 금액
- **Side Panel** — 선택된 이상치 상세: 동일 리소스의 14일 추이, 같은 cost_unit의 다른 리소스 비교, 원클릭 Slack 재알림

**URL 파라미터:** `?severity=critical&detector=zscore,arima&from=2024-01-01`

### 4.5 `/forecast` — 예측 & 편차

**목적:** "예측이랑 실제가 얼마나 달라?" (질문 3)

**구성 요소:**
- **Prophet Forecast Band 차트** — 전체 또는 cost_unit별 예측선·신뢰구간·실측선 오버레이
- **Variance Summary** — over / within_band / under 비율 도넛
- **Variance Bar 차트** — 리소스별 편차율, over/under 색상 분리
- **Infracost vs 실제** — Terraform 기반 예측과 실제 비교 테이블
- **Forecast Accuracy (Prophet CV)** — MAE / RMSE / MAPE 지표 카드

**URL 파라미터:** `?scope=team:platform&horizon=30`

### 4.6 `/budget` — 예산 관리

**목적:** "예산 대비 현황은?" (질문 4)

**구성 요소:**
- **상단 Summary** — 전체 예산·사용액·남은 금액·초과 팀 수
- **Budget Gauge Grid** — `(team, env)` 조합별 pill 카드, 사용률 progress bar
- **CRUD 인터페이스**
  - 예산 항목 추가 (team, env, amount, 와일드카드 지원)
  - 수정/삭제 (Radix Dialog)
  - 히스토리 (변경 감사 로그)
- **알림 설정** — warning/over threshold 조정 → `platform_settings` 업데이트

**URL 파라미터:** `?month=2024-01&status=warning,over`

### 4.7 `/chargeback` — 팀별 비용 배부

**구성 요소:**
- **Chargeback Treemap** — team → product → env 계층, 비용 비례 타일
- **Team Summary Table** — 팀별 총액·MoM 변화·점유율
- **CSV Export** — `data/reports/chargeback_YYYY-MM.csv` 다운로드

**URL 파라미터:** `?month=2024-01&groupBy=team`

### 4.8 `/recommendations` — 비용 최적화 추천

**목적:** Phase 7 `cost_recommendations` asset 시각화

**구성 요소:**
- **Recommendation Cards** — idle / high_growth / persistent_anomaly 3카테고리
- 각 카드: 리소스, 예상 절감액, 실행 가이드 (CLAUDE.md 파이프라인의 추천 규칙 연동)
- **Dismiss / Mark as Applied** 버튼 (상태는 DuckDB에 저장)

### 4.9 `/settings` — 운영 설정

**목적:** `platform_settings` 테이블 CRUD UI (Phase 7 Streamlit Settings 탭 계승)

**구성 요소:**
- **탭 전환**
  - Detectors — zscore/isolation_forest/moving_average/arima/autoencoder 활성화 + 파라미터
  - Thresholds — variance, alert, budget
  - Reporting — lookback, limits
  - Integrations — Slack webhook, Email SMTP, FX provider
- **변경 이력** — 누가·언제·무엇을 바꿨는지 (audit log)

### 4.10 `/pipeline` — 파이프라인 상태 (선택)

**목적:** Dagster materialization 상태 확인

**구성 요소:**
- Asset별 최근 실행 상태 (성공/실패/진행 중)
- 최근 실패 로그
- "Materialize all" 트리거 버튼 (Dagster GraphQL API 호출)

---

## 5. API 설계

FastAPI 기반, 모든 엔드포인트는 `/api` 프리픽스, JSON 응답, OpenAPI 자동 생성.

### 5.1 엔드포인트 일람

| Method | Path | 설명 | 주 쿼리 |
|---|---|---|---|
| GET | `/api/overview` | Overview 페이지 집계 | `month`, `currency` |
| GET | `/api/costs/summary` | 필터 조합 총액 | `providers`, `teams`, `services`, `from`, `to` |
| GET | `/api/costs/timeseries` | 일별 시계열 | 동일 |
| GET | `/api/costs/top-resources` | Top N 리소스 | `limit`, `lookback_days` |
| GET | `/api/costs/top-cost-units` | Top N cost_unit | 동일 |
| GET | `/api/costs/resource/{id}` | 리소스 상세 | — |
| GET | `/api/anomalies` | 이상치 목록 | `severity`, `detector`, `from`, `to` |
| GET | `/api/anomalies/{id}` | 이상치 상세 | — |
| GET | `/api/forecast/prophet` | Prophet 예측 | `scope`, `horizon` |
| GET | `/api/forecast/variance` | Variance 집계 | `month` |
| GET | `/api/forecast/accuracy` | Prophet CV 결과 | — |
| GET | `/api/budget` | 예산 목록 + 상태 | `month` |
| POST | `/api/budget` | 예산 추가 | Body: `{team, env, amount}` |
| PATCH | `/api/budget/{id}` | 예산 수정 | — |
| DELETE | `/api/budget/{id}` | 예산 삭제 | — |
| GET | `/api/chargeback` | 팀별 배부 | `month`, `groupBy` |
| GET | `/api/recommendations` | 추천 목록 | `status` |
| PATCH | `/api/recommendations/{id}` | 상태 변경 (dismiss/applied) | — |
| GET | `/api/settings` | 전체 설정 | — |
| PATCH | `/api/settings` | 부분 업데이트 | Body: `{key, value}` |
| GET | `/api/fx` | 환율 목록 | `base` |
| GET | `/api/pipeline/status` | Dagster asset 상태 | — |

### 5.2 응답 스키마 (예시)

**`GET /api/costs/top-resources`**

```json
{
  "month": "2024-01",
  "currency": "USD",
  "total_count": 127,
  "items": [
    {
      "resource_id": "aws_instance.web_1",
      "provider": "aws",
      "service": "EC2",
      "region": "us-east-1",
      "cost_unit_key": "platform:api:prod",
      "effective_cost": "12345.678900",
      "list_cost": "13800.000000",
      "mom_change_pct": 8.3,
      "tags": {"team": "platform", "product": "api", "env": "prod"}
    }
  ]
}
```

**공통 규칙:**
- 금액은 항상 **문자열**로 반환 (`Decimal(18,6)` 정밀도 보존). 프런트에서 `decimal.js`로 포맷.
- 날짜는 ISO 8601 (`2024-01-15T00:00:00Z`).
- 모든 응답에 `meta: { generated_at, currency, cache_ttl_sec }` 포함.

### 5.3 성능 전략

- **DuckDB 연결 풀링** — FastAPI 앱 생명주기에 연결 1개 유지, read-only 모드
- **캐시** — `GET` 응답에 `Cache-Control: max-age=60` + TanStack Query `staleTime`
- **페이징** — 100건 초과 테이블은 offset/limit, 무한 스크롤 또는 페이지네이션
- **집계 SQL은 뷰 재사용** — `v_top_resources_30d`, `v_top_cost_units_30d`, `v_variance` 그대로 쿼리

---

## 6. 레이아웃 구조

### 6.1 전체 쉘 (Arc 스타일)

```
┌──────────────────────────────────────────────────────────────────┐
│  Sidebar (240px)  │  TopBar (64px, sticky)                       │
│  ────────────────  │  ──────────────────────────────────────────  │
│  [Logo]            │  [MonthPicker] [CurrencyPicker] [Search] [⚙] │
│                    │                                               │
│  Overview          │  ┌──────────────────────────────────────┐    │
│  Costs             │  │                                       │    │
│  Anomalies         │  │       Page Content                    │    │
│  Forecast          │  │       (max-width: 1440px, padding)    │    │
│  Budget            │  │                                       │    │
│  Chargeback        │  │                                       │    │
│  Recommendations   │  │                                       │    │
│  ────────────      │  │                                       │    │
│  Settings          │  │                                       │    │
│  Pipeline          │  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### 6.2 Sidebar (`components/layout/Sidebar.tsx`)

- 너비 240px, 배경 `--bg-warm-subtle`, 우측 1px border
- 항목: `Phosphor` 아이콘 20px + 라벨 (Inter 14px 500)
- 활성 항목: `--text-primary` + 좌측 2px 악센트 bar + 살짝 배경 (`rgba(0,0,0,0.04)`)
- 모바일: 햄버거로 접힘, `Radix Dialog` 기반 슬라이드

### 6.3 TopBar (`components/layout/TopBar.tsx`)

- 높이 64px, sticky, `--bg-warm` + 하단 1px border
- 좌측: 현재 페이지 breadcrumb (Inter 14px secondary)
- 우측: `MonthPicker`, `CurrencySelector` (FX 적용), Search (`⌘K`), Settings shortcut

### 6.4 PageHeader (`components/layout/PageHeader.tsx`)

- Instrument Serif 48px 제목 + Inter 15px secondary 설명
- 우측: 페이지별 primary action (Export, Refresh 등)
- 제목 아래 32px 여백 후 콘텐츠

---

## 7. 핵심 컴포넌트 동작 규칙

### 7.1 금액 표시 (`formatters.ts`)

`docs/design-system.md` §8의 규칙 준수.

```ts
formatCurrency("12345.678900", "USD")
// → <span class="font-mono tabular-nums">
//     <span class="text-[0.7em] opacity-80">$</span>12,345<span class="opacity-60">.68</span>
//   </span>
```

- 1M 이상: `$12.3M`
- 천 단위 구분
- 소수점 기본 2자리, 상세 테이블 옵션 6자리

### 7.2 Severity Badge (`components/status/SeverityBadge.tsx`)

```tsx
<SeverityBadge severity="critical" />
// pill 모양 (radius-full), 배경 critical 20% opacity, 텍스트 critical 100%, 1px border
```

- `critical` → `--status-critical`
- `warning` → `--status-warning`
- `healthy` → `--status-healthy`

### 7.3 Trend Indicator

```tsx
<TrendIndicator value={12.3} context="cost" />
// → ▲ +12.3%  (red, cost 맥락에서 증가는 bad)

<TrendIndicator value={-8.1} context="savings" />
// → ▼ -8.1%  (red, savings 맥락에서 감소는 bad)
```

`context` prop으로 증가/감소의 색상 의미 반전. 기본은 `cost`.

### 7.4 Filter 상태는 URL에 (nuqs)

```ts
const [providers, setProviders] = useQueryState(
  'providers',
  parseAsArrayOf(parseAsString).withDefault(['aws', 'gcp', 'azure'])
)
```

- 모든 필터·정렬·페이지 번호가 URL에 반영
- 새 탭 복사, 북마크, Slack 공유가 그대로 동작
- 페이지 mount 시 URL → 상태 복원

### 7.5 차트 라이브러리 선택 기준

- **Recharts**: 선/바/영역/도넛/스캐터 → 빠른 구현, design-system 색상 주입 쉬움
- **D3**: Treemap, 계층 시각화, 커스텀 인터랙션이 필요한 경우만
- **Plotly 금지** (Streamlit 전용)

모든 차트 컴포넌트는 `docs/design-system.md` §10 Signature Charts 규격 준수.

---

## 8. 데이터 흐름

```
Dagster 파이프라인 (주기 실행)
  ↓ materialize
DuckDB (data/marts.duckdb)
  ↓ read-only
FastAPI (api/)
  ↓ JSON
Next.js Server Components (data fetching)
  ↓ streaming / hydration
Client Components (TanStack Query cache)
  ↓ polling / refetch
UI 렌더
```

### 8.1 캐시 계층

1. **TanStack Query** — 클라이언트 측, `staleTime: 60s`, `refetchOnWindowFocus: true`
2. **Next.js `fetch` cache** — 서버 컴포넌트 `revalidate: 60`
3. **FastAPI 응답 헤더** — `Cache-Control: public, max-age=60`
4. **DuckDB** — 자체 쿼리 캐시

### 8.2 실시간 업데이트

- Overview·Anomalies 페이지: 60초 polling
- Pipeline 페이지: 10초 polling (파이프라인 상태)
- (향후) Server-Sent Events 또는 WebSocket으로 이상치 신규 발생 push

### 8.3 에러 처리

- 모든 API 호출은 TanStack Query `onError`로 toast 표시 (Radix Toast)
- 치명적 에러: Next.js `error.tsx` boundary
- 빈 상태: 차트·테이블마다 전용 empty state (일러스트 + 안내 문구 + CTA)

---

## 9. 로컬 실행

### 9.1 Docker Compose

```yaml
services:
  api:
    build: ./api
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data:ro     # DuckDB 읽기 전용
      - ./config:/app/config:ro
    environment:
      - DUCKDB_PATH=/app/data/marts.duckdb

  web-app:
    build: ./web-app
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_BASE=http://api:8000
    depends_on:
      - api
```

### 9.2 실행 순서

```bash
# 1. 파이프라인으로 DuckDB 채우기
uv run dagster dev   # 전체 assets materialize

# 2. 웹 앱 + API 기동
docker compose up

# 3. http://localhost:3000 접속
```

### 9.3 개발 모드 (Docker 없이)

```bash
# 터미널 1
cd api && uv run uvicorn main:app --reload --port 8000

# 터미널 2
cd web-app && pnpm dev
```

---

## 10. 테스트 전략

| 레이어 | 도구 | 범위 |
|---|---|---|
| 백엔드 단위 | pytest | API 라우터, 스키마 검증, DuckDB 쿼리 |
| 백엔드 통합 | pytest + httpx | `api/tests/` — 실제 DuckDB에 대한 엔드투엔드 |
| 프런트 단위 | Vitest + React Testing Library | formatter, 훅, 순수 컴포넌트 |
| E2E | Playwright | 주요 유저 플로우 (필터 → drill-down → export) |
| 시각 회귀 | Playwright + screenshot | 페이지별 스크린샷 비교 (선택) |

**커버리지 목표:** API 90%, 프런트 핵심 유틸 80%, E2E는 페이지당 최소 1 happy path.

---

## 11. 접근성 & 반응형

### 11.1 접근성

- Radix UI 기반 → 키보드 네비·스크린리더 기본 지원
- 모든 상호작용 요소에 `aria-label` 명시
- 색상 의미는 **반드시 텍스트·아이콘과 병행** (색각이상 대응)
- 차트: 데이터 테이블 alternative 제공 (`aria-describedby`)
- Lighthouse Accessibility ≥ 95

### 11.2 반응형 브레이크포인트

- `sm`: 640px — 사이드바 햄버거로 전환
- `md`: 768px — 그리드 단일 컬럼으로
- `lg`: 1024px — 기본 레이아웃
- `xl`: 1280px — 확장 레이아웃 (Top N 표시 개수 증가)

모바일에서도 KPI·주요 차트는 항상 표시. 테이블은 카드 리스트로 재구성.

---

## 12. 오픈소스 쇼케이스 연계

### 12.1 랜딩페이지 (`web/`)와의 관계

- `web/` — 마케팅·GitHub 유입용 **랜딩페이지** (별도 Vercel 배포)
- `web-app/` — 실제 **모니터링 애플리케이션** (Docker 배포)
- 랜딩의 "Live Demo" 버튼이 `web-app`의 데모 인스턴스로 링크
- 두 앱은 `docs/design-system.md`를 공유하여 브랜드 일관성 유지

### 12.2 데모 인스턴스

- **공개 데모 URL** (예: `demo.finops-platform.dev`)
- Dagster 파이프라인의 생성기(seed 고정)로 만든 **합성 데이터** 사용 (실제 클라우드 비용 아님)
- 접속자는 읽기 전용, 설정 변경은 세션 단위 샌드박스

### 12.3 스크린샷 자동화

- Playwright로 모든 페이지를 light/dark 모드로 캡처 → `docs/screenshots/`에 저장
- GitHub Actions에서 PR마다 시각 회귀 확인 (선택)
- README·랜딩페이지가 동일 스크린샷 참조

---

## 13. 구현 단계 (Phase 8 제안)

### Phase 8.1 — 기반 세팅
- `api/`, `web-app/` 디렉토리 생성, 기본 스캐폴딩
- Docker Compose, 개발 모드 실행 확인
- `docs/design-system.md` 토큰을 `tailwind.config.ts` + `globals.css`에 반영
- 레이아웃 쉘 (Sidebar + TopBar + PageHeader) 완성

### Phase 8.2 — Overview 페이지 MVP
- `/api/overview` 엔드포인트
- KPI 카드 4개 + Stacked Area + Top 5 카드
- URL 상태 관리 (월 선택)

### Phase 8.3 — Costs 익스플로러
- 필터 패널, Treemap, DataTable, Resource drill-down
- CSV export

### Phase 8.4 — Anomalies + Forecast
- Anomaly Scatter + 상세 side panel
- Prophet Forecast Band + Variance 분석

### Phase 8.5 — Budget + Chargeback + Recommendations
- Budget CRUD, Chargeback Treemap, Recommendations 카드

### Phase 8.6 — Settings + Pipeline
- platform_settings CRUD UI
- Dagster 상태 연동

### Phase 8.7 — Polish
- 반응형·접근성·에러 바운더리
- E2E 테스트
- 데모 인스턴스 배포
- 스크린샷 촬영 → 랜딩페이지·README 업데이트

### Phase 8.8 — Streamlit Deprecation
- `scripts/streamlit_app.py`를 "Legacy internal tool"로 라벨
- 새 기여자는 `web-app/`으로 유도
- 최종적으로 Streamlit은 읽기 전용 디버깅 도구로만 유지

---

## 14. 금지 사항

- **Streamlit 로직을 그대로 포팅하지 말 것** — 새 UX로 재설계
- **Plotly 사용 금지** — Recharts + D3로 통일
- **shadcn/ui 컴포넌트 기본 스타일 그대로 사용 금지** — Radix primitive + 커스텀 스타일
- **디자인 토큰 하드코딩 금지** — 반드시 `design-system.md`의 CSS 변수·Tailwind 토큰 사용
- **이모지 아이콘 금지** — Phosphor 또는 SVG
- **브랜드 원색 금지** — AWS 오렌지, GCP 파랑, Azure 파랑 대신 muted palette
- **금액을 `number` 타입으로 다루지 말 것** — API는 string, 프런트는 `decimal.js` 또는 `bignumber.js`
- **"modern", "clean", "sleek" 프롬프트로 회귀 금지**

---

## 15. CLAUDE.md·design-system.md와의 관계

- **CLAUDE.md** — 데이터 파이프라인·도메인 모델·Phase 히스토리 (백엔드 중심)
- **docs/design-system.md** — 시각 디자인 토큰 (단일 소스 오브 트루스)
- **docs/monitoring-webapp.md** (이 문서) — 모니터링 웹 앱의 구조·페이지·API·동작 (기능 중심)

수정 시 원칙:
- 데이터 모델 변경 → `CLAUDE.md` 업데이트 → 이 문서 영향 범위 점검
- 디자인 토큰 변경 → `design-system.md` 업데이트 → 이 문서의 컴포넌트 규칙 재확인
- UI 구조·페이지 추가 → 이 문서 업데이트