# FinOps Platform

로컬 환경에서 돌아가는 FinOps 플랫폼. AWS CUR(가상) 데이터를 Medallion 아키텍처로 처리하고 Infracost 예측 대비 실제 비용 편차를 분석한다.

## 핵심 질문

1. **지금 가장 많은 비용을 발생시키는 게 뭐야?** — Top-N 비용 드라이버 (서비스·리소스·팀·태그별)
2. **예측이랑 실제가 얼마나 달라?** — Forecast vs Actual Variance 분석

## 아키텍처

```
raw_cur → [Pydantic 검증] → bronze_iceberg → silver_focus → gold_marts
                                                                  ↑
terraform/sample → infracost_forecast ────────────────── variance (CSV)
```

## 기술 스택

| 레이어 | 도구 |
|---|---|
| Orchestrator | Dagster ≥1.8 |
| 전처리 | Polars ≥1.0 |
| Table Format | Apache Iceberg (PyIceberg) |
| Analytics | DuckDB ≥1.0 |
| Validation | Pydantic v2 |
| Cost Forecast | Infracost CLI |

## 실행 방법

```bash
# 의존성 설치
uv sync --extra dev

# 환경 설정
cp .env.example .env

# Infracost CLI 설치 (Step 11 필요)
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh
infracost configure set api_key <YOUR_KEY>

# Dagster 실행
uv run dagster dev
# → http://localhost:3000

# 테스트
uv run pytest --cov=dagster_project --cov-fail-under=70

# 린트 / 타입 체크
uv run ruff check .
uv run mypy dagster_project
```

## 디렉토리 구조

```
finops-platform/
├── dagster_project/     # Dagster assets, resources, schemas, core
├── terraform/sample/    # Infracost 분석 대상 IaC
├── sql/marts/           # Silver→Gold SQL
├── tests/               # pytest 테스트
└── data/                # 생성된 데이터 (gitignored)
```
