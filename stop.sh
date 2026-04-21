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

for pidfile in "$PID_DIR"/*.pid; do
    [ -f "$pidfile" ] || continue
    pid=$(cat "$pidfile")
    name=$(basename "$pidfile" .pid)

    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        info "$name (PID $pid) 정지됨"
    else
        warn "$name (PID $pid) 이미 종료되어 있음"
    fi
    rm -f "$pidfile"
done

info "모든 서비스가 종료되었습니다."
