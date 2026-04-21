#!/usr/bin/env bash
# ==============================================================================
#  FinOps Platform — one-shot installer
#  Supports: macOS (Homebrew), Debian/Ubuntu (apt), RHEL/Fedora (dnf/yum),
#            Arch (pacman), Alpine (apk), WSL2 (detected as Linux)
#
#  What this script does:
#    1) Detect OS / package manager
#    2) Install system deps: git, curl, build-essentials, postgresql, node, uv
#    3) Bootstrap .env from .env.example
#    4) uv sync (Python 3.14, Python packages)
#    5) Initialise PostgreSQL — create role finops_app + DB finops
#    6) npm install + npm run build in web-app/
#    7) Optionally install Infracost CLI (--with-infracost)
#    8) Print next-step instructions
#
#  Usage:
#    ./install.sh                    # full install
#    ./install.sh --skip-system      # skip OS package install (CI / locked-down hosts)
#    ./install.sh --skip-build       # skip Next.js production build
#    ./install.sh --with-infracost   # also install Infracost CLI
#    ./install.sh --help
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# ── Colours ───────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
else
  GREEN=''; YELLOW=''; CYAN=''; RED=''; NC=''
fi

info()  { echo -e "${GREEN}[install]${NC} $*"; }
step()  { echo -e "${CYAN}[install]${NC} $*"; }
warn()  { echo -e "${YELLOW}[install]${NC} $*"; }
error() { echo -e "${RED}[install]${NC} $*" >&2; exit 1; }

# ── Flags ─────────────────────────────────────────────────────────────────────
SKIP_SYSTEM=0
SKIP_BUILD=0
WITH_INFRACOST=0
for arg in "$@"; do
  case "$arg" in
    --skip-system)    SKIP_SYSTEM=1 ;;
    --skip-build)     SKIP_BUILD=1 ;;
    --with-infracost) WITH_INFRACOST=1 ;;
    -h|--help)
      sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) error "알 수 없는 옵션: $arg" ;;
  esac
done

# ── Detect OS / package manager ───────────────────────────────────────────────
OS_KIND="unknown"   # macos | debian | rhel | arch | alpine | linux
PKG=""              # brew | apt | dnf | pacman | apk

if [[ "$OSTYPE" == "darwin"* ]]; then
  OS_KIND="macos"
  PKG="brew"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    case "${ID:-}:${ID_LIKE:-}" in
      *debian*|*ubuntu*) OS_KIND="debian"; PKG="apt" ;;
      *rhel*|*fedora*|*centos*|*rocky*|*almalinux*)
        OS_KIND="rhel"; PKG=$(command -v dnf >/dev/null 2>&1 && echo dnf || echo yum) ;;
      *arch*)   OS_KIND="arch";   PKG="pacman" ;;
      *alpine*) OS_KIND="alpine"; PKG="apk" ;;
      *) OS_KIND="linux" ;;
    esac
  fi
else
  OS_KIND="unknown"
fi

info "감지된 OS: ${OS_KIND} / 패키지 매니저: ${PKG:-none}"

# ── sudo helper ───────────────────────────────────────────────────────────────
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then SUDO="sudo"; fi
fi

# ── Package install helper ────────────────────────────────────────────────────
pkg_install() {
  local pkgs=("$@")
  [ ${#pkgs[@]} -eq 0 ] && return 0
  case "$PKG" in
    brew)
      for p in "${pkgs[@]}"; do
        brew list --formula "$p" >/dev/null 2>&1 || brew install "$p"
      done ;;
    apt)
      $SUDO apt-get update -y
      $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}" ;;
    dnf|yum)
      $SUDO $PKG install -y "${pkgs[@]}" ;;
    pacman)
      $SUDO pacman -Syu --noconfirm --needed "${pkgs[@]}" ;;
    apk)
      $SUDO apk add --no-cache "${pkgs[@]}" ;;
    *)
      warn "지원하지 않는 패키지 매니저 — ${pkgs[*]} 를 수동 설치하세요." ;;
  esac
}

# ── 0. Install Homebrew on macOS if missing ───────────────────────────────────
if [ "$OS_KIND" = "macos" ] && ! command -v brew >/dev/null 2>&1; then
  if [ $SKIP_SYSTEM -eq 0 ]; then
    step "Homebrew 설치 중..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"; fi
    if [ -x /usr/local/bin/brew ];   then eval "$(/usr/local/bin/brew shellenv)"; fi
  else
    warn "--skip-system 지정 — Homebrew 설치 건너뜀"
  fi
fi

# ── 1. System packages ────────────────────────────────────────────────────────
if [ $SKIP_SYSTEM -eq 0 ]; then
  step "1) 시스템 패키지 설치"
  case "$OS_KIND" in
    macos)
      pkg_install git curl postgresql@16 node
      brew services start postgresql@16 >/dev/null 2>&1 || true
      # Add postgres@16 binaries to PATH for this session
      BREW_PREFIX="$(brew --prefix)"
      export PATH="${BREW_PREFIX}/opt/postgresql@16/bin:$PATH"
      ;;
    debian)
      pkg_install git curl build-essential ca-certificates \
                  postgresql postgresql-contrib libpq-dev
      # Node.js 20 (NodeSource)
      if ! command -v node >/dev/null 2>&1; then
        curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO -E bash -
        pkg_install nodejs
      fi
      $SUDO systemctl enable --now postgresql >/dev/null 2>&1 || \
        $SUDO service postgresql start >/dev/null 2>&1 || true
      ;;
    rhel)
      pkg_install git curl gcc gcc-c++ make postgresql-server postgresql-contrib
      if ! command -v node >/dev/null 2>&1; then
        curl -fsSL https://rpm.nodesource.com/setup_20.x | $SUDO bash -
        pkg_install nodejs
      fi
      # Initialise cluster on first run
      if [ ! -d /var/lib/pgsql/data/base ]; then
        $SUDO postgresql-setup --initdb >/dev/null 2>&1 || true
      fi
      $SUDO systemctl enable --now postgresql >/dev/null 2>&1 || true
      ;;
    arch)
      pkg_install git curl base-devel postgresql nodejs npm
      if [ ! -d /var/lib/postgres/data/base ]; then
        $SUDO -u postgres initdb -D /var/lib/postgres/data >/dev/null 2>&1 || true
      fi
      $SUDO systemctl enable --now postgresql >/dev/null 2>&1 || true
      ;;
    alpine)
      pkg_install git curl build-base postgresql postgresql-contrib nodejs npm
      $SUDO rc-service postgresql start >/dev/null 2>&1 || true
      $SUDO rc-update add postgresql default >/dev/null 2>&1 || true
      ;;
    *)
      warn "자동 시스템 설치 미지원 — git/curl/postgresql/node 를 수동 설치하세요." ;;
  esac
else
  warn "--skip-system 지정 — 시스템 패키지 설치 건너뜀"
fi

# ── 2. Install uv (Python package manager) ────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
  step "2) uv 설치"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Add ~/.local/bin to PATH for this session
  export PATH="$HOME/.local/bin:$PATH"
else
  info "uv 이미 설치됨: $(uv --version)"
fi

# ── 3. Environment file ───────────────────────────────────────────────────────
step "3) .env 파일 준비"
if [ ! -f ".env" ]; then
  cp .env.example .env
  info ".env 생성 (.env.example 복사)"
else
  info ".env 이미 존재 — 유지"
fi

# ── 4. Python dependencies ────────────────────────────────────────────────────
step "4) Python 의존성 설치 (uv sync)"
uv sync

# ── 5. Data directories ───────────────────────────────────────────────────────
step "5) 데이터 디렉토리 생성"
mkdir -p data/warehouse data/reports .dagster

# ── 6. PostgreSQL bootstrap ───────────────────────────────────────────────────
step "6) PostgreSQL 초기화 (finops DB + finops_app role)"

# Load values from .env
set -o allexport
# shellcheck disable=SC1091
source .env
set +o allexport

PG_HOST="${POSTGRES_HOST:-localhost}"
PG_PORT="${POSTGRES_PORT:-5432}"
PG_DB="${POSTGRES_DBNAME:-finops}"
PG_USER="${POSTGRES_USER:-finops_app}"
PG_PASS="${POSTGRES_PASSWORD:-finops_secret_2026}"

# Pick a superuser-capable psql invocation
PG_SU=""
if [ "$OS_KIND" = "macos" ]; then
  # Homebrew postgres runs as the current user
  PG_SU="psql -h $PG_HOST -p $PG_PORT -d postgres"
else
  PG_SU="$SUDO -u postgres psql -h $PG_HOST -p $PG_PORT -d postgres"
fi

# Wait for postgres to accept connections (max ~30s)
ready=0
for i in $(seq 1 30); do
  if $PG_SU -tAc "SELECT 1" >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
if [ $ready -ne 1 ]; then
  warn "PostgreSQL에 연결할 수 없습니다. 수동으로 기동한 뒤 아래를 실행하세요:"
  warn "  createdb ${PG_DB}"
  warn "  createuser ${PG_USER} --pwprompt"
else
  # Create role if missing
  exists=$($PG_SU -tAc "SELECT 1 FROM pg_roles WHERE rolname='${PG_USER}'" 2>/dev/null || true)
  if [ "$exists" != "1" ]; then
    $PG_SU -c "CREATE ROLE ${PG_USER} WITH LOGIN CREATEDB PASSWORD '${PG_PASS}'" >/dev/null
    info "Role ${PG_USER} 생성"
  else
    info "Role ${PG_USER} 이미 존재"
  fi

  # Create DB if missing
  db_exists=$($PG_SU -tAc "SELECT 1 FROM pg_database WHERE datname='${PG_DB}'" 2>/dev/null || true)
  if [ "$db_exists" != "1" ]; then
    $PG_SU -c "CREATE DATABASE ${PG_DB} OWNER ${PG_USER}" >/dev/null
    info "Database ${PG_DB} 생성 (owner=${PG_USER})"
  else
    info "Database ${PG_DB} 이미 존재"
  fi

  # Grant schema privileges (public schema in new PG >=15 defaults may be restrictive)
  $PG_SU -d "${PG_DB}" -c "GRANT ALL ON SCHEMA public TO ${PG_USER}" >/dev/null 2>&1 || true
  $PG_SU -d "${PG_DB}" -c "ALTER SCHEMA public OWNER TO ${PG_USER}" >/dev/null 2>&1 || true

  # Connectivity check as finops_app
  if PGPASSWORD="${PG_PASS}" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
      -tAc "SELECT 1" >/dev/null 2>&1; then
    info "PostgreSQL 연결 확인: ${PG_USER}@${PG_HOST}:${PG_PORT}/${PG_DB}"
  else
    warn "PostgreSQL 연결 실패 — pg_hba.conf에 local md5/scram 인증을 허용하세요."
  fi
fi

# ── 6.5 Initialise analytics schema ──────────────────────────────────────────
step "6.5) 분석 마트 스키마 초기화 (dagster_project/db_schema.py)"
uv run python scripts/init_db.py || warn "init_db.py 실행 실패 — 수동으로 다시 실행하세요."

# ── 7. Web dashboard deps & build ─────────────────────────────────────────────
step "7) Dashboard (web-app) 의존성 설치"
if [ -d web-app ]; then
  (cd web-app && npm install)
  if [ $SKIP_BUILD -eq 0 ]; then
    step "7.1) Dashboard 프로덕션 빌드"
    (cd web-app && npm run build)
  else
    warn "--skip-build 지정 — npm run build 건너뜀 (개발 모드로 실행 가능)"
  fi
else
  warn "web-app/ 디렉토리가 없어 건너뜀"
fi

# ── 8. Infracost CLI (optional) ───────────────────────────────────────────────
if [ $WITH_INFRACOST -eq 1 ]; then
  step "8) Infracost CLI 설치"
  if ! command -v infracost >/dev/null 2>&1; then
    curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh
    info "Infracost 설치 완료 — 'infracost configure set api_key <KEY>' 를 실행하세요."
  else
    info "Infracost 이미 설치됨: $(infracost --version | head -1)"
  fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  FinOps 설치 완료.${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "다음 명령으로 전체 서비스 기동:"
echo "  ./start.sh                         # Dagster + FastAPI + Dashboard"
echo ""
echo "개별 기동:"
echo "  uv run dagster dev                 # Dagster UI  (http://localhost:3000)"
echo "  uv run uvicorn api.main:app --port 8000 --reload   # FastAPI"
echo "  (cd web-app && npm run dev)        # Dashboard   (http://localhost:3002)"
echo ""
echo "테스트:"
echo "  uv run pytest -q"
echo ""
