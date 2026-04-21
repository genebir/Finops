#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

info()    { echo -e "${GREEN}[start]${NC} $*"; }
warn()    { echo -e "${YELLOW}[start]${NC} $*"; }
error()   { echo -e "${RED}[start]${NC} $*" >&2; exit 1; }
dim()     { echo -e "${DIM}$*${NC}"; }

# ── 옵션 파싱 ─────────────────────────────────────────────────────────────────
WITH_STREAMLIT=false
for arg in "$@"; do
    case "$arg" in
        --streamlit)   WITH_STREAMLIT=true ;;
        --help|-h)
            echo "사용법: ./start.sh [옵션]"
            echo ""
            echo "옵션:"
            echo "  --streamlit    Streamlit 대시보드도 함께 시작 (기본: 비활성)"
            echo "  --help         이 도움말 표시"
            echo ""
            echo "서비스:"
            echo "  Dagster        http://localhost:3000"
            echo "  FastAPI        http://localhost:8000"
            echo "  Next.js        http://localhost:3002"
            echo "  Streamlit      http://localhost:8501  (--streamlit 옵션 시)"
            exit 0
            ;;
    esac
done

PID_DIR="$ROOT_DIR/.pids"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

# ── 종료 핸들러 ───────────────────────────────────────────────────────────────
cleanup() {
    echo ""
    warn "종료 신호 수신. 서비스를 정지합니다..."

    for pidfile in "$PID_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        pid=$(cat "$pidfile")
        name=$(basename "$pidfile" .pid)
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && info "$name (PID $pid) 정지됨"
        fi
        rm -f "$pidfile"
    done

    info "모든 서비스가 종료되었습니다."
}
trap cleanup EXIT INT TERM

# ── 이미 실행 중인지 확인 ────────────────────────────────────────────────────
for pidfile in "$PID_DIR"/*.pid; do
    [ -f "$pidfile" ] || continue
    pid=$(cat "$pidfile")
    name=$(basename "$pidfile" .pid)
    if kill -0 "$pid" 2>/dev/null; then
        error "$name 이(가) 이미 실행 중입니다 (PID $pid). 먼저 ./stop.sh 를 실행하세요."
    else
        rm -f "$pidfile"
    fi
done

# ── 사전 조건 확인 ───────────────────────────────────────────────────────────
info "사전 조건 확인 중..."

[ -f "uv.lock" ]                   || error "uv.lock이 없습니다. 먼저 ./deploy.sh 를 실행하세요."
[ -d "web-app/node_modules" ]      || error "web-app/node_modules가 없습니다. 먼저 ./deploy.sh 를 실행하세요."
[ -d "web-app/.next" ]             || error "web-app/.next가 없습니다. 먼저 ./deploy.sh 를 실행하세요. (npm run build 필요)"
[ -f ".env" ]                      || error ".env 파일이 없습니다. 먼저 ./deploy.sh 를 실행하세요."

# .env 로드
set -o allexport
# shellcheck source=/dev/null
source .env
set +o allexport

# PostgreSQL 연결 확인
PG_HOST="${POSTGRES_HOST:-localhost}"
PG_PORT="${POSTGRES_PORT:-5432}"
if command -v pg_isready >/dev/null 2>&1; then
    pg_isready -h "$PG_HOST" -p "$PG_PORT" -q \
        || error "PostgreSQL에 연결할 수 없습니다 ($PG_HOST:$PG_PORT). DB가 실행 중인지 확인하세요."
    info "PostgreSQL 연결 확인 완료 ($PG_HOST:$PG_PORT)"
elif command -v nc >/dev/null 2>&1; then
    nc -z "$PG_HOST" "$PG_PORT" 2>/dev/null \
        || error "PostgreSQL에 연결할 수 없습니다 ($PG_HOST:$PG_PORT). DB가 실행 중인지 확인하세요."
    info "PostgreSQL 포트 확인 완료 ($PG_HOST:$PG_PORT)"
else
    warn "pg_isready / nc 없음 — PostgreSQL 연결 확인 생략"
fi

# ── 헬스체크 유틸 ────────────────────────────────────────────────────────────
wait_for_http() {
    local name="$1"
    local url="$2"
    local timeout="${3:-30}"
    local elapsed=0

    printf "${DIM}  %s 기동 대기 중" "$name"
    while ! curl -sf "$url" >/dev/null 2>&1; do
        sleep 1
        elapsed=$((elapsed + 1))
        printf "."
        if [ "$elapsed" -ge "$timeout" ]; then
            echo ""
            warn "$name 이 ${timeout}초 내에 응답하지 않습니다. 로그를 확인하세요."
            return 1
        fi
    done
    echo -e " ${GREEN}✓${NC}"
    return 0
}

# ── 1. Dagster ────────────────────────────────────────────────────────────────
info "Dagster 시작 중..."
uv run dagster dev \
    --host 0.0.0.0 \
    --port 3000 \
    > "$LOG_DIR/dagster.log" 2>&1 &
echo $! > "$PID_DIR/dagster.pid"
dim "  PID $(cat "$PID_DIR/dagster.pid") | 로그: logs/dagster.log"

# ── 2. FastAPI ───────────────────────────────────────────────────────────────
info "FastAPI 시작 중..."
uv run uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    > "$LOG_DIR/api.log" 2>&1 &
echo $! > "$PID_DIR/api.pid"
dim "  PID $(cat "$PID_DIR/api.pid") | 로그: logs/api.log"

# ── 3. Next.js 대시보드 ───────────────────────────────────────────────────────
info "Next.js 대시보드 시작 중..."
cd web-app
PORT=3002 npm start \
    > "$LOG_DIR/dashboard.log" 2>&1 &
echo $! > "$PID_DIR/dashboard.pid"
cd "$ROOT_DIR"
dim "  PID $(cat "$PID_DIR/dashboard.pid") | 로그: logs/dashboard.log"

# ── 4. Streamlit (선택) ───────────────────────────────────────────────────────
if [ "$WITH_STREAMLIT" = true ]; then
    info "Streamlit 시작 중..."
    uv run streamlit run scripts/streamlit_app.py \
        --server.port 8501 \
        --server.address 0.0.0.0 \
        --server.headless true \
        > "$LOG_DIR/streamlit.log" 2>&1 &
    echo $! > "$PID_DIR/streamlit.pid"
    dim "  PID $(cat "$PID_DIR/streamlit.pid") | 로그: logs/streamlit.log"
fi

# ── 헬스체크 ─────────────────────────────────────────────────────────────────
echo ""
info "서비스 기동 확인 중..."

HEALTH_OK=true
wait_for_http "FastAPI"        "http://localhost:8000/health"  30 || HEALTH_OK=false
wait_for_http "Next.js"        "http://localhost:3002"         45 || HEALTH_OK=false
wait_for_http "Dagster"        "http://localhost:3000"         60 || HEALTH_OK=false
if [ "$WITH_STREAMLIT" = true ]; then
    wait_for_http "Streamlit"  "http://localhost:8501"         30 || HEALTH_OK=false
fi

# ── 상태 출력 ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  FinOps Platform 실행 중${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  대시보드              →  ${GREEN}http://localhost:3002/overview${NC}"
echo -e "  FastAPI 문서          →  ${GREEN}http://localhost:8000/docs${NC}"
echo -e "  Dagster Orchestrator  →  ${GREEN}http://localhost:3000${NC}"
if [ "$WITH_STREAMLIT" = true ]; then
    echo -e "  Streamlit (디버그)    →  ${GREEN}http://localhost:8501${NC}"
fi
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  로그 확인: ${DIM}tail -f logs/api.log logs/dashboard.log${NC}"
echo -e "  종료:      ${YELLOW}Ctrl+C${NC}  또는  ${YELLOW}./stop.sh${NC}"
echo ""

if [ "$HEALTH_OK" = false ]; then
    warn "일부 서비스가 정상 기동되지 않았을 수 있습니다. 로그를 확인하세요."
fi

# ── 서비스 감시 루프 ──────────────────────────────────────────────────────────
# 5초마다 프로세스 생존 확인 → 죽으면 경고
while true; do
    sleep 5
    for pidfile in "$PID_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        pid=$(cat "$pidfile")
        name=$(basename "$pidfile" .pid)
        if ! kill -0 "$pid" 2>/dev/null; then
            warn "${name} (PID $pid) 이 예기치 않게 종료되었습니다. logs/${name}.log 를 확인하세요."
            rm -f "$pidfile"
        fi
    done

    # 모든 서비스가 죽었으면 종료
    if [ -z "$(ls -A "$PID_DIR" 2>/dev/null)" ]; then
        error "모든 서비스가 종료되었습니다."
    fi
done
