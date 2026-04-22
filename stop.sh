#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[stop]${NC} $*"; }
warn()  { echo -e "${YELLOW}[stop]${NC} $*"; }

PID_DIR="$ROOT_DIR/.pids"

if [ ! -d "$PID_DIR" ] || [ -z "$(ls -A "$PID_DIR" 2>/dev/null)" ]; then
    warn "실행 중인 서비스가 없습니다."
    exit 0
fi

STOPPED=0
ALREADY_DEAD=0

for pidfile in "$PID_DIR"/*.pid; do
    [ -f "$pidfile" ] || continue
    pid=$(cat "$pidfile")
    name=$(basename "$pidfile" .pid)

    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null
        # Graceful shutdown: 3초 대기
        for _ in 1 2 3 4 5 6; do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.5
        done
        # 아직 살아있으면 강제 종료
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
            info "$name (PID $pid) 강제 종료됨"
        else
            info "$name (PID $pid) 정지됨"
        fi
        STOPPED=$((STOPPED + 1))
    else
        warn "$name (PID $pid) 이미 종료되어 있음"
        ALREADY_DEAD=$((ALREADY_DEAD + 1))
    fi
    rm -f "$pidfile"
done

info "정지: ${STOPPED}개, 이미 종료: ${ALREADY_DEAD}개"
info "모든 서비스가 종료되었습니다."
