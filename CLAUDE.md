# FinOps Platform — Project Specification

> 이 문서는 Claude Code가 본 프로젝트를 스캐폴딩하고 **Phase 1 MVP**를 완성하는 데 필요한 모든 컨텍스트를 담고 있다.
> 모든 구현은 이 문서의 **Section 8 (구현 계획)** 순서를 따른다. 각 Step 완료 시 멈추고 확인 받는다.

---

## 1. 프로젝트 목표

로컬 환경에서 돌아가는 **FinOps 플랫폼**을 만든다. 플랫폼이 답해야 할 핵심 질문:

1. **"지금 가장 많은 비용을 발생시키는 게 뭐야?"** — Top-N 비용 드라이버 (서비스·리소스·팀·태그별)
2. **"이상하게 튄 비용이 있어?"** — 이상치 탐지 *(Phase 2)*
3. **"예측이랑 실제가 얼마나 달라?"** — Forecast vs Actual Variance 분석

**확장성 원칙:** 단일 AWS 가상 CUR → 멀티 클라우드 + 멀티 예측 소스 + 알림으로 **증분 확장**이 가능해야 한다. 이를 위해 `CostSource`, `ForecastProvider` 등 **Protocol 기반 추상화**를 Phase 1부터 도입한다.

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
| Cost Forecast | Infracost CLI | Terraform 기반 비용 예측 |
| Standard | FOCUS 1.0 | 비용 데이터 규격 |
| Language | Python 3.11+ | |
| Package Mgmt | uv | |
| Lint/Type | ruff + mypy (strict) | |

---

## 3. 아키텍처 개요 (Medallion + FinOps Layer)

```
┌─────────────────────────────────────────────────────────────┐
│  [raw_cur]  가상 AWS CUR 생성 (seeded, FOCUS 1.0)            │
│       │                                                      │
│       ▼                                                      │
│  [Pydantic 검증]  FocusRecord 모델로 레코드 단위 유효성 검사    │
│       │                                                      │
│       ▼                                                      │
│  [bronze_iceberg]  PyIceberg, 월별 파티션 (ChargePeriodStart)│
│       │                                                      │
│       ▼                                                      │
│  [silver_focus]  Polars: 태그 평탄화, CostUnit 파생           │
│       │                                                      │
│       ▼                                                      │
│  [gold_marts]  DuckDB:                                       │
│       - fact_daily_cost                                      │
│       - dim_cost_unit                                        │
│       - v_top_resources_30d                                  │
│       │                                                      │
│       │     [terraform/sample] ─▶ [infracost_forecast]       │
│       │            │                                         │
│       ▼            ▼                                         │
│  [variance]  ResourceId 기준 JOIN, 편차(%) 계산               │
│       │                                                      │
│       ▼                                                      │
│  data/reports/variance_YYYYMM.csv                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. FOCUS 1.0 구현 범위 (Phase 1)

FOCUS 1.0 필수 컬럼 중 **분석에 실제 쓰일 것들만** 구현. 나머지는 NULL 허용 또는 Phase 2 이월.

### 구현 대상 컬럼

- **Identifiers**: `BillingAccountId`, `SubAccountId`, `ResourceId`, `ResourceName`, `ResourceType`
- **Time**: `ChargePeriodStart`, `ChargePeriodEnd`, `BillingPeriodStart`, `BillingPeriodEnd` (모두 UTC)
- **Cost**: `BilledCost`, `EffectiveCost`, `ListCost`, `ContractedCost` — **모두 `Decimal(18,6)`**
- **Currency**: `BillingCurrency` (Phase 1은 `USD` 고정)
- **Service**: `ServiceName`, `ServiceCategory`, `ProviderName` (`AWS`)
- **Location**: `RegionId`, `RegionName`, `AvailabilityZone`
- **Charge**: `ChargeCategory` (Enum: `Usage|Purchase|Tax|Credit|Adjustment`), `ChargeDescription`
- **Usage**: `UsageQuantity`, `UsageUnit`, `PricingQuantity`, `PricingUnit`
- **SKU**: `SkuId`, `SkuPriceId`
- **Commitment**: `CommitmentDiscountCategory`, `CommitmentDiscountId`, `CommitmentDiscountType` (Phase 1 대부분 NULL)
- **Tags**: `Tags` (JSON 문자열 → Silver에서 평탄화)

### Tags 정책 (중요)

가상 CUR 생성기는 **모든 리소스에** 최소 다음 태그를 심는다:
- `team` (예: `platform`, `data`, `ml`, `frontend`)
- `product` (예: `checkout`, `search`, `recommender`)
- `env` (`prod` | `staging` | `dev`)

이 세 태그는 **Cost Unit 차원**의 기초가 된다 (Section 6.5 참고).

---

## 5. 디렉토리 구조

```
finops-platform/
├── CLAUDE.md                        # 이 문서
├── pyproject.toml
├── README.md
├── .env.example
├── .gitignore
├── dagster_project/
│   ├── __init__.py
│   ├── definitions.py               # Dagster Definitions 엔트리포인트
│   ├── assets/
│   │   ├── __init__.py
│   │   ├── raw_cur.py               # 가상 CUR 생성 asset
│   │   ├── bronze_iceberg.py        # Iceberg 적재
│   │   ├── silver_focus.py          # Polars 정제
│   │   ├── gold_marts.py            # DuckDB 마트
│   │   ├── infracost_forecast.py    # Infracost 실행 & 파싱
│   │   └── variance.py              # 편차 계산
│   ├── resources/
│   │   ├── __init__.py
│   │   ├── iceberg_catalog.py       # SqlCatalog 설정
│   │   ├── duckdb_io.py             # DuckDB 커넥션 매니저
│   │   └── infracost_cli.py         # Infracost CLI wrapper
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── focus_v1.py              # Pydantic FocusRecord
│   ├── core/                        # 확장 포인트 (추상 인터페이스)
│   │   ├── __init__.py
│   │   ├── cost_source.py           # CostSource Protocol
│   │   ├── forecast_provider.py     # ForecastProvider Protocol
│   │   └── cost_unit.py             # CostUnit 차원 정의
│   └── generators/
│       └── aws_cur_generator.py     # CostSource 구현체 (가상 AWS)
├── terraform/
│   └── sample/                      # Infracost 분석 대상 IaC
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── sql/
│   └── marts/                       # Silver→Gold SQL
│       ├── fact_daily_cost.sql
│       ├── dim_cost_unit.sql
│       ├── v_top_resources_30d.sql
│       └── v_variance.sql
├── data/                            # gitignored
│   ├── warehouse/                   # Iceberg 데이터
│   ├── catalog.db                   # SqlCatalog SQLite
│   ├── marts.duckdb                 # DuckDB 파일
│   └── reports/                     # 출력 CSV
└── tests/
    ├── conftest.py
    ├── test_focus_schema.py
    ├── test_cur_generator.py
    ├── test_idempotency.py
    ├── test_silver_transforms.py
    └── test_variance.py
```

---

## 6. 핵심 추상화 (확장 포인트)

Phase 1부터 **Protocol로 선언**하고 주입식으로 쓴다. 확장성의 핵심.

### 6.1 `CostSource` — `dagster_project/core/cost_source.py`

```python
from typing import Protocol, Iterable
from datetime import date
from ..schemas.focus_v1 import FocusRecord

class CostSource(Protocol):
    name: str  # "aws" | "gcp" | "azure"

    def generate(self, period_start: date, period_end: date) -> Iterable[FocusRecord]:
        """지정된 기간의 FOCUS 규격 비용 레코드를 yield."""
        ...
```

Phase 1 구현체: `AwsCurGenerator` (가상).
Phase 3 예정: `GcpBillingExport`, `AzureCostExport`.

### 6.2 `ForecastProvider` — `dagster_project/core/forecast_provider.py`

```python
class ForecastProvider(Protocol):
    name: str  # "infracost" | "prophet" | "manual_budget"

    def forecast(self, scope: ForecastScope) -> list[ForecastRecord]:
        ...
```

Phase 1 구현체: `InfracostProvider`.
Phase 2 예정: `ProphetProvider` (시계열 기반).

### 6.3 `AnomalyDetector` — Phase 2
### 6.4 `AlertSink` — Phase 2

### 6.5 `CostUnit` 차원 — `dagster_project/core/cost_unit.py` **(매우 중요)**

모든 비용 데이터는 **Cost Unit**으로 환원 가능해야 한다:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CostUnit:
    team: str
    product: str
    env: str  # prod | staging | dev

    @classmethod
    def from_tags(cls, tags: dict[str, str]) -> "CostUnit":
        return cls(
            team=tags.get("team", "unknown"),
            product=tags.get("product", "unknown"),
            env=tags.get("env", "unknown"),
        )

    @property
    def key(self) -> str:
        return f"{self.team}:{self.product}:{self.env}"
```

Silver 레이어에서 Tags → CostUnit을 파생한다. 미래에 쿼리 비용·SaaS 비용이 붙어도 같은 CostUnit으로 집계되어 **팀별 총소유비용(TCO)** 을 단일 뷰로 볼 수 있다. 이 설계가 확장성의 핵심.

---

## 7. 주요 설계 결정

| 항목 | 결정 |
|---|---|
| **Infracost 조인 키** | 옵션 (b): 가상 CUR 생성 시 terraform 리소스 주소(`aws_instance.web`)를 `ResourceId`로 심어 자동 매칭. `CostSource`에 `resource_id_strategy` 필드를 두어 추후 교체 가능. |
| **파티셔닝** | Iceberg 테이블은 `ChargePeriodStart` **월 단위** 파티션 |
| **멱등성** | 동일 `(BillingAccountId, ChargePeriodStart[month])` 파티션에 대해 `overwrite`. **append 금지.** |
| **통화** | Phase 1은 USD 고정. FX 변환은 Phase 3. |
| **시간대** | 모든 timestamp는 **UTC**. Silver에서 `ChargePeriodStartUtc` 컬럼 유지. |
| **Cost 타입** | `Decimal(18,6)` — float 절대 금지 |
| **랜덤 시드** | CUR 생성기는 `seed=42` 기본값. 환경변수 `CUR_SEED`로 override. |

---

## 8. Phase 1 MVP — 구현 계획 (순서 엄수)

### Step 1: 프로젝트 부트스트랩
- `uv init finops-platform` → `pyproject.toml` 작성
- Runtime deps: `dagster`, `dagster-webserver`, `polars`, `duckdb`, `pyiceberg[sql-sqlite,pyarrow]`, `pydantic`, `python-dotenv`, `rich`, `pyarrow`
- Dev deps: `pytest`, `pytest-cov`, `ruff`, `mypy`
- `.env.example`, `.gitignore` (data/, .venv/, __pycache__/, .dagster/)
- `README.md` 기본 버전

### Step 2: FOCUS 1.0 Pydantic 스키마 — `schemas/focus_v1.py`
- `FocusRecord` 모델 (Section 4의 모든 필드)
- `ChargeCategory`, `ServiceCategory` Enum
- Validator:
  - `ChargePeriodEnd > ChargePeriodStart`
  - `EffectiveCost <= ListCost`
  - `BillingCurrency == "USD"` (Phase 1)
  - `Tags`가 JSON 문자열이면 파싱 가능해야 함
- `to_pyarrow_row()` 헬퍼 (PyIceberg 쓰기용)

### Step 3: Cost Unit 차원 — `core/cost_unit.py`
- Section 6.5 그대로 구현
- 단위 테스트: `from_tags` 누락 케이스

### Step 4: Cost Source 추상화 + 가상 AWS CUR 생성기
- `core/cost_source.py`: Protocol 선언
- `generators/aws_cur_generator.py`: `AwsCurGenerator` 구현
  - **Seeded** (`random.Random(seed)`) → 같은 입력이면 같은 출력
  - 서비스 분포: EC2 40%, RDS 20%, S3 15%, Lambda 10%, 기타 15%
  - 리소스 10~30개, 각 리소스가 월 내 일별 ChargePeriod 발생
  - 태그(team/product/env) 현실적 분포
  - **의도적 이상치 1~2개** — 평균 대비 5배 이상 튀는 리소스 (탐지 테스트용)
  - Infracost 매칭용 리소스는 `ResourceId`를 `aws_<type>.<name>` 포맷으로 (예: `aws_instance.web_1`)

### Step 5: Iceberg 카탈로그 리소스 — `resources/iceberg_catalog.py`
- Dagster `ConfigurableResource`
- `SqlCatalog` with SQLite backend, warehouse=`data/warehouse/`
- 메서드: `ensure_namespace(name)`, `ensure_table(name, schema, partition_spec)`

### Step 6: Raw CUR Asset — `assets/raw_cur.py`
- `@asset(partitions_def=MonthlyPartitionsDefinition(start_date="2024-01-01"))`
- `AwsCurGenerator`로 해당 월의 FocusRecord 리스트 생성
- **출력 전 Pydantic 검증** (모든 레코드)
- 반환: `list[FocusRecord]` (메모리 전달)

### Step 7: Bronze Iceberg Asset — `assets/bronze_iceberg.py`
- `raw_cur`를 입력받아 PyArrow Table로 변환
- Iceberg `focus.bronze_cur` 테이블에 `overwrite` (해당 월 파티션만)
- 멱등성 필수

### Step 8: Silver Asset — `assets/silver_focus.py`
- Polars로 Bronze 읽기 (`pyiceberg.catalog.load_table().scan().to_polars()`)
- Tags JSON → `team`, `product`, `env` 컬럼 분리
- `cost_unit_key` 생성 (`team:product:env`)
- Iceberg `focus.silver_focus` 네임스페이스로 쓰기

### Step 9: Gold 마트 SQL + Asset — `sql/marts/*.sql`, `assets/gold_marts.py`
- DuckDB가 Iceberg 테이블을 읽을 수 있도록 `iceberg` extension 로드 후 `ATTACH`
- `fact_daily_cost`: 일×리소스×CostUnit별 집계
- `dim_cost_unit`: 고유 CostUnit 마스터
- `v_top_resources_30d`: 최근 30일 Top-20 리소스 (effective_cost 기준)
- `v_top_cost_units_30d`: 최근 30일 Top-10 Cost Unit

### Step 10: Terraform 샘플 — `terraform/sample/main.tf`
- EC2 5개, RDS 2개, S3 3개
- 리소스 이름을 CUR 생성기와 **반드시 일치**시킴 (조인 가능해야 함)
- 태그도 동일하게 `team`, `product`, `env` 부여

### Step 11: Infracost Provider & Asset
- `resources/infracost_cli.py`: `infracost breakdown --path terraform/sample --format json` 실행
- `core/forecast_provider.py`: Protocol 선언
- `assets/infracost_forecast.py`: JSON 파싱 → `dim_forecast` 테이블 (DuckDB)
  - 컬럼: `resource_address`, `monthly_cost`, `hourly_cost`, `currency`, `forecast_generated_at`

### Step 12: Variance Asset — `assets/variance.py`
- Infracost 예측(`dim_forecast`) **LEFT JOIN** 실제 비용(`fact_daily_cost` 월 집계) on `resource_id = resource_address`
- 컬럼:
  - `resource_id`
  - `forecast_monthly` (Decimal)
  - `actual_mtd` (Decimal)
  - `variance_abs = actual_mtd - forecast_monthly`
  - `variance_pct = (actual_mtd - forecast_monthly) / forecast_monthly * 100`
  - `status`: `over` (>+20%) | `under` (<-20%) | `ok` | `unmatched` (forecast NULL)
- 출력: `data/reports/variance_YYYYMM.csv`

### Step 13: Dagster Definitions & 전체 실행
- `definitions.py`에서 모든 asset, resource 등록
- `uv run dagster dev` → http://localhost:3000 → 전체 DAG materialize
- 검증: `data/reports/variance_<당월>.csv` 생성 확인

### Step 14: 테스트
- `test_focus_schema.py`: invalid 레코드 reject (음수 비용, 잘못된 날짜 등)
- `test_cur_generator.py`: 동일 seed → 동일 해시
- `test_idempotency.py`: Bronze asset 2회 materialize → row count 및 해시 동일
- `test_silver_transforms.py`: Tags → CostUnit 파생 정확성
- `test_variance.py`: 예측 > 실제, 예측 < 실제, unmatched 케이스
- 커버리지: `pytest --cov=dagster_project --cov-fail-under=70`

---

## 9. 코딩 컨벤션

- Python 3.11+, **모든 함수에 완전한 타입 힌트**
- `ruff` (line-length=100) + `mypy --strict` 통과 필수
- 금액은 **반드시 `decimal.Decimal`** (float 절대 금지)
- 날짜는 `datetime.date`, 시각은 `datetime.datetime` with `tzinfo=UTC`
- I/O 사이드이펙트 있는 코드는 `@asset`으로만. 순수 함수는 `core/`, `schemas/`에.
- 모든 asset에 docstring + Dagster `description` 필수
- 로깅은 Dagster `context.log.info/warning/error` (print 금지)
- 예외 처리는 구체적 예외 타입으로 (`except Exception:` 지양)

---

## 10. 멱등성 체크리스트

- [ ] CUR 생성기 `seed` 고정 시 동일 출력 (해시 검증)
- [ ] Iceberg Bronze는 파티션 단위 `overwrite` (append 금지)
- [ ] DuckDB Gold는 `CREATE OR REPLACE TABLE`
- [ ] Infracost는 terraform plan 해시 기준 캐시 (동일 tf → 동일 forecast)
- [ ] 전체 파이프라인 2회 실행 후 출력 CSV 바이트 단위 동일

---

## 11. 실행 방법

```bash
# 부트스트랩
uv sync
cp .env.example .env

# Infracost CLI 설치 (별도)
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh
infracost configure set api_key <YOUR_KEY>

# Dagster 실행
uv run dagster dev
# → http://localhost:3000 → 전체 assets materialize

# 테스트
uv run pytest

# 린트 / 타입 체크
uv run ruff check .
uv run mypy dagster_project
```

---

## 12. Phase 1 Out of Scope (나중에)

- 이상치 탐지 (→ Phase 2)
- 알림 (Slack/Email) (→ Phase 2)
- 시계열 기반 예측 (Prophet 등) (→ Phase 2)
- 멀티 클라우드 (GCP/Azure) (→ Phase 3)
- 실제 AWS CUR 연동 (→ Phase 3)
- FX 통화 변환 (→ Phase 3)
- 프론트엔드 대시보드 (별도 결정)
