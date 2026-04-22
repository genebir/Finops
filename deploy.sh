#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

info()    { echo -e "${GREEN}[deploy]${NC} $*"; }
step()    { echo -e "${CYAN}[deploy]${NC} $*"; }
warn()    { echo -e "${YELLOW}[deploy]${NC} $*"; }
error()   { echo -e "${RED}[deploy]${NC} $*" >&2; exit 1; }

# ── 옵션 파싱 ─────────────────────────────────────────────────────────────────
SKIP_BUILD=false
DEV_MODE=false
SKIP_DB=false

for arg in "$@"; do
    case "$arg" in
        --dev)          DEV_MODE=true ;;
        --skip-build)   SKIP_BUILD=true ;;
        --skip-db)      SKIP_DB=true ;;
        --help|-h)
            echo "사용법: ./deploy.sh [옵션]"
            echo ""
            echo "옵션:"
            echo "  --dev          개발 모드 (Next.js 프로덕션 빌드 생략)"
            echo "  --skip-build   Next.js ��드만 생략"
            echo "  --skip-db      PostgreSQL 초기화 단계 생략"
            echo "  --help         이 도움말 표시"
            exit 0
            ;;
        *) error "알 수 없는 옵션: $arg" ;;
    esac
done

if [ "$DEV_MODE" = true ]; then
    SKIP_BUILD=true
fi

# ── 1. 의존성 확인 ────────────────────────────────────────────────────────────
step "1) 의존성 확인"

MISSING=()
command -v uv   >/dev/null 2>&1 || MISSING+=("uv (https://docs.astral.sh/uv/)")
command -v node >/dev/null 2>&1 || MISSING+=("node (https://nodejs.org/)")
command -v npm  >/dev/null 2>&1 || MISSING+=("npm")

if [ ${#MISSING[@]} -gt 0 ]; then
    error "필수 도구가 없습니다:\n$(printf '  - %s\n' "${MISSING[@]}")\n\n./install.sh 를 먼저 실행하거나 직접 설치하세요."
fi

info "Python: $(uv run python --version 2>/dev/null || echo 'managed by uv')"
info "Node:   $(node --version)"
info "npm:    $(npm --version)"

# ── 2. 환경변�� 파일 ─────────────────────────────────────────────────────────
step "2) 환경변수 파일 확��"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        warn ".env 파일이 없어 .env.example을 복사했습니다. 필요 시 값을 수정하세요."
    else
        error ".env.example 파일이 없습니��."
    fi
else
    info ".env 파일 확인 완료"
fi

# .env 로드
set -o allexport
# shellcheck source=/dev/null
source .env
set +o allexport

# ── 3. Python 의존성 설치 ─────────────────────────────────────────────────────
step "3) Python 패키지 설치 (uv sync)"
uv sync

# ── 4. 데이터 디렉토리 생성 ──────────────────────────────────────────────────
step "4) 데이터 디렉토리 생성"
mkdir -p data/warehouse data/reports logs .dagster

# ── 5. PostgreSQL 확��� & 스키마 초기화 ────────────────────────────────────���───
if [ "$SKIP_DB" = false ]; then
    step "5) PostgreSQL 연결 확인 & 스키마 초기��"

    PG_HOST="${POSTGRES_HOST:-localhost}"
    PG_PORT="${POSTGRES_PORT:-5432}"
    PG_DB="${POSTGRES_DBNAME:-finops}"
    PG_USER="${POSTGRES_USER:-finops_app}"

    # 연결 확인
    PG_OK=false
    if command -v pg_isready >/dev/null 2>&1; then
        if pg_isready -h "$PG_HOST" -p "$PG_PORT" -q 2>/dev/null; then
            PG_OK=true
            info "PostgreSQL 연결 확인 ���료 ($PG_HOST:$PG_PORT)"
        fi
    elif command -v nc >/dev/null 2>&1; then
        if nc -z "$PG_HOST" "$PG_PORT" 2>/dev/null; then
            PG_OK=true
            info "PostgreSQL 포트 응답 확인 ($PG_HOST:$PG_PORT)"
        fi
    else
        warn "pg_isready / nc 없음 — PostgreSQL 연결 확인 생략, 스키마 초기화 시도"
        PG_OK=true
    fi

    if [ "$PG_OK" = true ]; then
        # DB 접속 확인 (finops_app 사용자)
        if PGPASSWORD="${POSTGRES_PASSWORD:-finops_secret_2026}" psql \
            -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
            -tAc "SELECT 1" >/dev/null 2>&1; then
            info "DB 접속 확인: ${PG_USER}@${PG_DB}"
        else
            warn "DB 접속 실패 — DB/Role이 없을 수 있습니다."
            warn "./install.sh 를 실행하거�� 수동으로 DB를 생성하세요:"
            warn "  CREATE ROLE ${PG_USER} WITH LOGIN CREATEDB PASSWORD '...';"
            warn "  CREATE DATABASE ${PG_DB} OWNER ${PG_USER};"
        fi

        # 스키마 초기화 (테이블 생성 + 설정 seed)
        info "스키마 초기화 실행 중 (init_db.py)..."
        if uv run python scripts/init_db.py 2>/dev/null; then
            info "스키마 초기화 완료"
        else
            warn "스키마 초기화 실패 — DB 연결을 확인하세요. 서비스 시작 시 자동 재시도됩니다."
        fi
    else
        warn "PostgreSQL에 연결할 수 없습니다 ($PG_HOST:$PG_PORT)"
        warn "DB가 실행 중인지 확인하세요. 서비스 시작 시 연결 실패 발생 가능."
    fi
else
    info "5) PostgreSQL 초기화 생략 (--skip-db)"
fi

# ── 6. Next.js 대시보드 의존성 설치 + 빌드 ────────────────────────────────────
step "6) Dashboard (web-app/) 패키지 설치"

if [ ! -d "web-app" ]; then
    error "web-app/ 디렉토리가 없습니다."
fi

cd web-app
npm install

if [ "$SKIP_BUILD" = false ]; then
    step "6.1) Dashboard 프로덕션 빌드"
    npm run build
    info "프로덕션 빌드 완료 (web-app/.next/)"
else
    if [ "$DEV_MODE" = true ]; then
        info "개발 모드 — 프로덕션 빌드 생략 (npm run dev 로 실행 가능)"
    else
        info "빌드 생략 (--skip-build)"
    fi
fi
cd "$ROOT_DIR"

# ── 7. 최종 검증 ─────────────────────────────────────────────────────────────
step "7) 최종 검증"

CHECKS_OK=true

# Python 패키지 확인
for pkg in dagster fastapi polars psycopg2; do
    if uv run python -c "import $pkg" 2>/dev/null; then
        info "  $pkg ✓"
    else
        warn "  $pkg ✗ (import 실패)"
        CHECKS_OK=false
    fi
done

# Dagster definitions 로드 확인
if uv run python -c "from dagster_project.definitions import defs; print(f'  assets: {len(list(defs.resolve_asset_graph().get_all_asset_keys()))}')" 2>/dev/null; then
    info "  Dagster definitions ✓"
else
    warn "  Dagster definitions 로드 실패"
    CHECKS_OK=false
fi

# FastAPI import 확인
if uv run python -c "from api.main import app; print(f'  routes: {len(app.routes)}')" 2>/dev/null; then
    info "  FastAPI app ✓"
else
    warn "  FastAPI app import 실패"
    CHECKS_OK=false
fi

# Next.js 빌드 확인
if [ "$SKIP_BUILD" = false ] && [ -d "web-app/.next" ]; then
    info "  Next.js build ✓"
elif [ "$DEV_MODE" = true ]; then
    info "  Next.js (dev mode — 빌드 불필���)"
else
    warn "  Next.js 빌드 없음 — ./start.sh --dev 로 실행하거��� 다시 deploy 하세요."
fi

# ── 완료 ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ "$CHECKS_OK" = true ]; then
    echo -e "${GREEN}  배포 완료. 이제 ./start.sh 를 실행하세요.${NC}"
else
    echo -e "${YELLOW}  배포 완료 (일부 경고 있음). 위 메시지를 확인하세요.${NC}"
fi
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
if [ "$DEV_MODE" = true ]; then
    echo -e "  실행: ${CYAN}./start.sh --dev${NC}"
else
    echo -e "  실행: ${CYAN}./start.sh${NC}"
fi
echo -e "  종료: ${CYAN}./stop.sh${NC}"
echo ""
