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
DEV_MODE=false
NO_DAGSTER=false
OPEN_BROWSER=false

for arg in "$@"; do
    case "$arg" in
        --streamlit)   WITH_STREAMLIT=true ;;
        --dev)         DEV_MODE=true ;;
        --no-dagster)  NO_DAGSTER=true ;;
        --open)        OPEN_BROWSER=true ;;
        --help|-h)
            echo "사용법: ./start.sh [옵션]"
            echo ""
            echo "옵션:"
            echo "  --dev          개발 모드 (Next.js dev server + FastAPI reload)"
            echo "  --no-dagster   Dagster 없이 시작 (API + Dashboard만)"
            echo "  --streamlit    Streamlit 대시보드도 함께 시작"
            echo "  --open         시작 후 브라우저 자동 열기"
            echo "  --help         이 도움말 표시"
            echo ""
            echo "서비스:"
            echo "  Dagster        http://localhost:3000"
            echo "  FastAPI        http://localhost:8000   (/docs 에서 Swagger UI)"
            echo "  Dashboard      http://localhost:3002   (메인 대시보드)"
            echo "  Streamlit      http://localhost:8501   (--streamlit 옵션 시)"
            echo ""
            echo "예시:"
            echo "  ./start.sh                     # 전체 프로덕션 기동"
            echo "  ./start.sh --dev               # 개발 모드 (hot-reload)"
            echo "  ./start.sh --dev --no-dagster  # 빠른 프론트엔드 개발"
            echo "  ./start.sh --open              # 기동 후 브라우저 열기"
            exit 0
            ;;
        *) error "알 수 없는 옵션: $arg  (--help 로 도움말 확인)" ;;
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
            kill "$pid" 2>/dev/null
            # 2초 대기 후 강제 종료
            for _ in 1 2 3 4; do
                kill -0 "$pid" 2>/dev/null || break
                sleep 0.5
            done
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
                info "$name (PID $pid) 강제 종료됨"
            else
                info "$name (PID $pid) 정지됨"
            fi
        fi
        rm -f "$pidfile"
    done

    info "모든 서비스가 종료되었습니다."
}
trap cleanup EXIT INT TERM

# ── 이미 실행 중인 서비스 확인 ────────────────────────────────────────────────
ALREADY_RUNNING=()
for pidfile in "$PID_DIR"/*.pid; do
    [ -f "$pidfile" ] || continue
    pid=$(cat "$pidfile")
    name=$(basename "$pidfile" .pid)
    if kill -0 "$pid" 2>/dev/null; then
        ALREADY_RUNNING+=("$name(PID:$pid)")
    else
        rm -f "$pidfile"
    fi
done

if [ ${#ALREADY_RUNNING[@]} -gt 0 ]; then
    error "이미 실행 중인 서비스가 있습니다: ${ALREADY_RUNNING[*]}\n먼저 ./stop.sh 를 실행하세요."
fi

# ── 포트 충돌 확인 ────────────────────────────────────────────────────────────
check_port() {
    local port="$1"
    local name="$2"
    if command -v lsof >/dev/null 2>&1; then
        local pid
        pid=$(lsof -ti :"$port" 2>/dev/null | head -1 || true)
        if [ -n "$pid" ]; then
            local cmd
            cmd=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
            warn "포트 $port 이 이미 사용 중입니다 (PID $pid: $cmd) — $name 시작 실패 가능"
            return 1
        fi
    elif command -v ss >/dev/null 2>&1; then
        if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
            warn "포트 $port 이 이미 사용 중입니다 — $name 시작 실패 가능"
            return 1
        fi
    fi
    return 0
}

info "포트 충돌 확인 중..."
PORT_OK=true
check_port 8000 "FastAPI"    || PORT_OK=false
check_port 3002 "Dashboard"  || PORT_OK=false
if [ "$NO_DAGSTER" = false ]; then
    check_port 3000 "Dagster" || PORT_OK=false
fi
if [ "$WITH_STREAMLIT" = true ]; then
    check_port 8501 "Streamlit" || PORT_OK=false
fi
if [ "$PORT_OK" = true ]; then
    info "포트 확인 완료"
fi

# ── 사전 조건 확인 ───────────────────────────────────────────────────────────
info "사전 조건 확인 중..."

[ -f "uv.lock" ]              || error "uv.lock이 없습니다. 먼저 ./deploy.sh 를 실행하세요."
[ -d "web-app/node_modules" ] || error "web-app/node_modules가 없습니다. 먼저 ./deploy.sh 를 실행하세요."
[ -f ".env" ]                 || error ".env 파일이 없습니다. 먼저 ./deploy.sh 를 실행하세요."

if [ "$DEV_MODE" = false ] && [ ! -d "web-app/.next" ]; then
    error "web-app/.next가 없습니다. ./deploy.sh 를 실행하거나 --dev 모드를 사용하세요."
fi

# .env 로드
set -o allexport
# shellcheck source=/dev/null
source .env
set +o allexport

# ── PostgreSQL 연결 확인 ────────────────────────────────────────────────────
PG_HOST="${POSTGRES_HOST:-localhost}"
PG_PORT="${POSTGRES_PORT:-5432}"
PG_DB="${POSTGRES_DBNAME:-finops}"
PG_USER="${POSTGRES_USER:-finops_app}"

PG_CONNECTED=false
if command -v pg_isready >/dev/null 2>&1; then
    if pg_isready -h "$PG_HOST" -p "$PG_PORT" -q 2>/dev/null; then
        PG_CONNECTED=true
        info "PostgreSQL 연결 확인 완료 ($PG_HOST:$PG_PORT)"
    fi
elif command -v nc >/dev/null 2>&1; then
    if nc -z "$PG_HOST" "$PG_PORT" 2>/dev/null; then
        PG_CONNECTED=true
        info "PostgreSQL 포트 확인 완료 ($PG_HOST:$PG_PORT)"
    fi
else
    warn "pg_isready / nc 없음 — PostgreSQL 연결 확인 생략"
    PG_CONNECTED=true
fi

if [ "$PG_CONNECTED" = false ]; then
    error "PostgreSQL에 연결할 수 없습니다 ($PG_HOST:$PG_PORT).\nDB가 실행 중인지 확인하세요.\n\n  sudo systemctl start postgresql  (Linux)\n  brew services start postgresql   (macOS)"
fi

# ── DB 스키마 자동 부트스트랩 ────────────────────────────────────────────────
info "DB 스키마 확인 중..."
if uv run python scripts/init_db.py > "$LOG_DIR/init_db.log" 2>&1; then
    info "DB 스키마 준비 완료"
else
    warn "DB 스키마 초기화 실패 — logs/init_db.log 확인. 계속 진행합니다."
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
            warn "$name 이 ${timeout}초 내에 응답하지 않습니다. logs/ 를 확인하세요."
            return 1
        fi
    done
    echo -e " ${GREEN}✓${NC}"
    return 0
}

# ── 서비스 시작 ──────────────────────────────────────────────────────────────

# 1. Dagster
if [ "$NO_DAGSTER" = false ]; then
    info "Dagster 시작 중..."
    uv run dagster dev \
        --host 0.0.0.0 \
        --port 3000 \
        > "$LOG_DIR/dagster.log" 2>&1 &
    echo $! > "$PID_DIR/dagster.pid"
    dim "  PID $(cat "$PID_DIR/dagster.pid") | 로그: logs/dagster.log"
else
    info "Dagster 생략 (--no-dagster)"
fi

# 2. FastAPI
info "FastAPI 시작 중..."
if [ "$DEV_MODE" = true ]; then
    uv run uvicorn api.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --reload-dir api \
        > "$LOG_DIR/api.log" 2>&1 &
else
    uv run uvicorn api.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        > "$LOG_DIR/api.log" 2>&1 &
fi
echo $! > "$PID_DIR/api.pid"
dim "  PID $(cat "$PID_DIR/api.pid") | 로그: logs/api.log"

# 3. Next.js 대시보드
info "Next.js 대시보드 시작 중..."
cd web-app
if [ "$DEV_MODE" = true ]; then
    PORT=3002 npm run dev \
        > "$LOG_DIR/dashboard.log" 2>&1 &
else
    PORT=3002 npm start \
        > "$LOG_DIR/dashboard.log" 2>&1 &
fi
echo $! > "$PID_DIR/dashboard.pid"
cd "$ROOT_DIR"
dim "  PID $(cat "$PID_DIR/dashboard.pid") | 로그: logs/dashboard.log"

# 4. Streamlit (선택)
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
wait_for_http "Dashboard"      "http://localhost:3002"         45 || HEALTH_OK=false
if [ "$NO_DAGSTER" = false ]; then
    wait_for_http "Dagster"    "http://localhost:3000"         60 || HEALTH_OK=false
fi
if [ "$WITH_STREAMLIT" = true ]; then
    wait_for_http "Streamlit"  "http://localhost:8501"         30 || HEALTH_OK=false
fi

# ── API readiness 확인 ──────────────────────────────────────────────────────
READY_STATUS=$(curl -sf http://localhost:8000/api/ops/ready 2>/dev/null || echo '{"status":"error"}')
if echo "$READY_STATUS" | grep -q '"ready"'; then
    info "API readiness: ready (DB 접속 + 기본 테이블 확인 완료)"
else
    warn "API readiness: not ready — 파이프라인을 먼저 실행하세요."
    dim "  Pipeline 페이지: http://localhost:3002/pipeline"
    dim "  또는 Dagster UI: http://localhost:3000"
fi

# ── 브라우저 열기 ────────────────────────────────────────────────────────────
open_browser() {
    local url="$1"
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" 2>/dev/null &
    elif command -v open >/dev/null 2>&1; then
        open "$url" 2>/dev/null &
    elif command -v wslview >/dev/null 2>&1; then
        wslview "$url" 2>/dev/null &
    elif [ -n "${BROWSER:-}" ]; then
        "$BROWSER" "$url" 2>/dev/null &
    fi
}

if [ "$OPEN_BROWSER" = true ] && [ "$HEALTH_OK" = true ]; then
    open_browser "http://localhost:3002/overview"
fi

# ── 상태 출력 ─────────────────────────────────────────────────────────────────
MODE_LABEL=""
if [ "$DEV_MODE" = true ]; then
    MODE_LABEL=" ${YELLOW}(dev mode — hot reload 활성)${NC}"
fi

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  FinOps Platform 실행 중${MODE_LABEL}${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  대시보드              →  ${GREEN}http://localhost:3002/overview${NC}"
echo -e "  파이프라인 트리거     →  ${GREEN}http://localhost:3002/pipeline${NC}"
echo -e "  FastAPI Swagger       →  ${GREEN}http://localhost:8000/docs${NC}"
if [ "$NO_DAGSTER" = false ]; then
    echo -e "  Dagster Orchestrator  →  ${GREEN}http://localhost:3000${NC}"
fi
if [ "$WITH_STREAMLIT" = true ]; then
    echo -e "  Streamlit (디버그)    →  ${GREEN}http://localhost:8501${NC}"
fi
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  로그 확인:  ${DIM}tail -f logs/api.log logs/dashboard.log${NC}"
echo -e "  전체 로그:  ${DIM}ls -la logs/${NC}"
echo -e "  종료:       ${YELLOW}Ctrl+C${NC}  또는  ${YELLOW}./stop.sh${NC}"
echo ""

if [ "$HEALTH_OK" = false ]; then
    warn "일부 서비스가 정상 기동되지 않았을 수 있습니다. logs/ 디렉토리를 확인하세요."
fi

# ── 서비스 감시 루프 ──────────────────────────────────────────────────────────
while true; do
    sleep 5
    for pidfile in "$PID_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        pid=$(cat "$pidfile")
        name=$(basename "$pidfile" .pid)
        if ! kill -0 "$pid" 2>/dev/null; then
            warn "${name} (PID $pid) 이 예기치 않게 종료되었습니다."
            warn "  로그 확인: tail -50 logs/${name}.log"
            rm -f "$pidfile"
        fi
    done

    # 모든 서비스가 죽었으면 종료
    if [ -z "$(ls -A "$PID_DIR" 2>/dev/null)" ]; then
        error "모든 서비스가 종료되었습니다. logs/ 를 확인하세요."
    fi
done
