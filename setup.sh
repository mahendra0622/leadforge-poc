#!/usr/bin/env bash
# ============================================================
# FintelliPro POC — One-Command Setup Script
# Usage: bash setup.sh
# ============================================================
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "${GREEN}  ✓ $1${RESET}"; }
info() { echo -e "${CYAN}  → $1${RESET}"; }
warn() { echo -e "${YELLOW}  ⚠ $1${RESET}"; }
err()  { echo -e "${RED}  ✗ $1${RESET}"; exit 1; }
hdr()  { echo -e "\n${BOLD}${CYAN}$1${RESET}"; echo "  $(printf '─%.0s' {1..50})"; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║       FintelliPro POC Setup v1.0         ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ── Check prerequisites ────────────────────────────────────────
hdr "Step 1 — Checking prerequisites"

command -v python3 &>/dev/null || err "Python 3.11+ is required. Install from python.org"
command -v node    &>/dev/null || err "Node.js 18+ is required. Install from nodejs.org"
command -v docker  &>/dev/null || err "Docker Desktop is required. Install from docker.com"
command -v docker-compose &>/dev/null 2>&1 || command -v docker compose &>/dev/null || err "docker-compose is required"

PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
NODE_VER=$(node --version | sed 's/v//')

ok "Python $PYTHON_VER"
ok "Node $NODE_VER"
ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"

# ── Create .env if missing ─────────────────────────────────────
hdr "Step 2 — Environment configuration"

if [ ! -f ".env" ]; then
  cp .env.example .env
  ok "Created .env from template"
  warn "Add your API keys to .env:"
  warn "  ANTHROPIC_API_KEY=sk-ant-... (for live Claude AI)"
  warn "  APOLLO_API_KEY=...           (for live contact enrichment)"
  warn "  (The POC works without these using built-in mock data)"
else
  ok ".env already exists"
fi

# ── Start Docker services ──────────────────────────────────────
hdr "Step 3 — Starting PostgreSQL + Redis"

if docker compose version &>/dev/null 2>&1; then
  DC="docker compose"
else
  DC="docker-compose"
fi

info "Pulling images and starting database services..."
$DC up -d db redis

info "Waiting for PostgreSQL to be ready..."
MAX_WAIT=30
COUNT=0
until $DC exec -T db pg_isready -U fintellipro -q 2>/dev/null; do
  COUNT=$((COUNT+1))
  if [ $COUNT -ge $MAX_WAIT ]; then
    err "PostgreSQL did not start in time. Check: docker compose logs db"
  fi
  sleep 1
done
ok "PostgreSQL is ready"
ok "Redis is ready"

# ── Backend setup ──────────────────────────────────────────────
hdr "Step 4 — Setting up Python backend"

cd backend

if [ ! -d "venv" ]; then
  info "Creating Python virtual environment..."
  python3 -m venv venv
  ok "Virtual environment created"
fi

info "Installing Python dependencies..."
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
ok "Dependencies installed"

info "Running database seed..."
DATABASE_URL="postgresql://fintellipro:fintellipro_dev@localhost:5432/fintellipro" \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
APOLLO_API_KEY="${APOLLO_API_KEY:-}" \
SECRET_KEY="dev-secret-key-change-in-production" \
python seed.py

ok "Database seeded with demo data"
cd ..

# ── Frontend setup ─────────────────────────────────────────────
hdr "Step 5 — Setting up React frontend"

cd frontend
info "Installing Node.js dependencies..."
npm install --silent
ok "Frontend dependencies installed"
cd ..

# ── Summary ────────────────────────────────────────────────────
hdr "Setup Complete!"
echo ""
echo -e "  ${BOLD}Now run these commands in separate terminals:${RESET}"
echo ""
echo -e "  ${CYAN}Terminal 1 — Backend:${RESET}"
echo -e "  ${YELLOW}  cd backend && source venv/bin/activate${RESET}"
echo -e "  ${YELLOW}  uvicorn app.main:app --reload${RESET}"
echo ""
echo -e "  ${CYAN}Terminal 2 — Frontend:${RESET}"
echo -e "  ${YELLOW}  cd frontend && npm run dev${RESET}"
echo ""
echo -e "  ${BOLD}Then open:${RESET}"
echo -e "  ${GREEN}  Frontend:   http://localhost:3000${RESET}"
echo -e "  ${GREEN}  API Docs:   http://localhost:8000/docs${RESET}"
echo ""
echo -e "  ${BOLD}Login:${RESET}"
echo -e "  ${GREEN}  Email:    demo@fintellipro.com${RESET}"
echo -e "  ${GREEN}  Password: demo1234${RESET}"
echo ""
echo -e "  ${BOLD}Or run everything with Docker:${RESET}"
echo -e "  ${YELLOW}  docker compose up${RESET}"
echo ""
