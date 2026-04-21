#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[start]${NC} $*"; }
warn()  { echo -e "${YELLOW}[start]${NC} $*"; }
error() { echo -e "${RED}[start]${NC} $*" >&2; exit 1; }

PID_DIR="$ROOT_DIR/.pids"
mkdir -p "$PID_DIR"

# ── 종료 핸들러 ───────────────────────────────────────────────────────────────
cleanup() {
    echo ""
    warn "종료 신호 수신. 서비스를 정지합니다..."

    for pidfile in "$PID_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        pid=$(cat "$pidfile")
        name=$(basename "$pidfile" .pid)
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" && info "$name (PID $pid) 정지됨"
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
        error "$name 이(가) 이미 실행 중입니다 (PID $pid). 먼저 종료하세요."
    else
        rm -f "$pidfile"
    fi
done

# ── 배포 여부 확인 ───────────────────────────────────────────────────────────
[ -f "uv.lock" ]           || error "uv.lock이 없습니다. 먼저 ./deploy.sh 를 실행하세요."
[ -d "web-app/node_modules" ]  || error "web-app/node_modules가 없습니다. 먼저 ./deploy.sh 를 실행하세요."
[ -f ".env" ]              || error ".env 파일이 없습니다. 먼저 ./deploy.sh 를 실행하세요."

# .env 로드
set -o allexport
source .env
set +o allexport

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

# ── 1. Dagster ────────────────────────────────────────────────────────────────
info "Dagster 시작 중..."
uv run dagster dev \
    --host 0.0.0.0 \
    --port 3000 \
    > "$LOG_DIR/dagster.log" 2>&1 &
echo $! > "$PID_DIR/dagster.pid"
info "Dagster PID: $(cat $PID_DIR/dagster.pid) | 로그: logs/dagster.log"

# ── 2. Streamlit ──────────────────────────────────────────────────────────────
info "Streamlit 시작 중..."
uv run streamlit run scripts/streamlit_app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    > "$LOG_DIR/streamlit.log" 2>&1 &
echo $! > "$PID_DIR/streamlit.pid"
info "Streamlit PID: $(cat $PID_DIR/streamlit.pid) | 로그: logs/streamlit.log"

# ── 3. FastAPI ───────────────────────────────────────────────────────────────
info "FastAPI 시작 중..."
uv run uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    > "$LOG_DIR/api.log" 2>&1 &
echo $! > "$PID_DIR/api.pid"
info "FastAPI PID: $(cat $PID_DIR/api.pid) | 로그: logs/api.log"

# ── 4. Next.js 대시보드 ───────────────────────────────────────────────────────
info "Next.js 대시보드 시작 중..."
cd web-app
PORT=3002 npm start \
    > "$LOG_DIR/dashboard.log" 2>&1 &
echo $! > "$PID_DIR/dashboard.pid"
cd "$ROOT_DIR"
info "Next.js Dashboard PID: $(cat $PID_DIR/dashboard.pid) | 로그: logs/dashboard.log"

# ── 기동 대기 ────────────────────────────────────────────────────────────────
info "서비스 기동 대기 중..."
sleep 4

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  FinOps Platform 실행 중${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Dagster Orchestrator  →  ${GREEN}http://localhost:3000${NC}"
echo -e "  Streamlit Dashboard   →  ${GREEN}http://localhost:8501${NC}"
echo -e "  FastAPI (JSON)        →  ${GREEN}http://localhost:8000/api/overview${NC}"
echo -e "  Dashboard             →  ${GREEN}http://localhost:3002/overview${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  종료하려면 ${YELLOW}Ctrl+C${NC} 를 누르세요."
echo ""

# ── 대기 (Ctrl+C까지) ────────────────────────────────────────────────────────
wait
