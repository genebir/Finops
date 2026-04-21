#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()    { echo -e "${YELLOW}[deploy]${NC} $*"; }
error()   { echo -e "${RED}[deploy]${NC} $*" >&2; exit 1; }

# ── 1. 의존성 확인 ────────────────────────────────────────────────────────────
info "의존성 확인 중..."

command -v uv   >/dev/null 2>&1 || error "uv가 설치되어 있지 않습니다. https://docs.astral.sh/uv/"
command -v node >/dev/null 2>&1 || error "Node.js가 설치되어 있지 않습니다. https://nodejs.org/"
command -v npm  >/dev/null 2>&1 || error "npm이 설치되어 있지 않습니다."

info "Python: $(uv python find 2>/dev/null || echo 'managed by uv')"
info "Node:   $(node --version)"
info "npm:    $(npm --version)"

# ── 2. 환경변수 파일 ─────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    warn ".env 파일이 없어 .env.example을 복사했습니다. 필요 시 값을 수정하세요."
else
    info ".env 파일 확인 완료"
fi

# ── 3. Python 의존성 설치 ─────────────────────────────────────────────────────
info "Python 패키지 설치 중 (uv sync)..."
uv sync

# ── 4. 데이터 디렉토리 생성 ──────────────────────────────────────────────────
info "데이터 디렉토리 생성 중..."
mkdir -p data/warehouse data/reports

# ── 5. Next.js 대시보드 의존성 설치 + 빌드 ────────────────────────────────────
info "Dashboard (web-app/) 패키지 설치 중..."
cd web-app
npm install

info "Dashboard 프로덕션 빌드 중..."
npm run build
cd "$ROOT_DIR"

# ── 완료 ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  배포 완료. 이제 ./start.sh 를 실행하세요.${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
