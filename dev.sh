#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# REFINET Cloud — Local Development Launcher
#
# Starts both the backend API (port 8000) and frontend (port 3000).
# Ctrl+C kills both processes cleanly.
#
# Usage:
#   ./dev.sh           — start both servers
#   ./dev.sh api       — start only the backend
#   ./dev.sh frontend  — start only the frontend
# ─────────────────────────────────────────────────────────────────

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$ROOT_DIR"
FRONTEND_DIR="$ROOT_DIR/frontend"

# Colors
TEAL='\033[0;36m'
DIM='\033[0;90m'
BOLD='\033[1m'
NC='\033[0m'

cleanup() {
  echo ""
  echo -e "${DIM}Shutting down...${NC}"
  kill $API_PID 2>/dev/null
  kill $FE_PID 2>/dev/null
  wait $API_PID 2>/dev/null
  wait $FE_PID 2>/dev/null
  echo -e "${DIM}Done.${NC}"
}
trap cleanup EXIT INT TERM

# ── Preflight checks ──

if [ ! -f "$ROOT_DIR/.env" ]; then
  echo -e "${BOLD}Error:${NC} .env file not found. Copy .env.example to .env first."
  exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo -e "${TEAL}Installing frontend dependencies...${NC}"
  (cd "$FRONTEND_DIR" && npm install)
fi

# Check Python venv
VENV="$ROOT_DIR/.venv"
if [ -d "$VENV" ]; then
  source "$VENV/bin/activate"
elif [ -d "$ROOT_DIR/venv" ]; then
  VENV="$ROOT_DIR/venv"
  source "$VENV/bin/activate"
fi

# ── Start servers ──

start_api() {
  echo -e "${TEAL}Starting API server${NC} ${DIM}→ http://localhost:8000${NC}"
  (cd "$API_DIR" && uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload 2>&1 | sed "s/^/  [api] /") &
  API_PID=$!
}

start_frontend() {
  echo -e "${TEAL}Starting frontend${NC}    ${DIM}→ http://localhost:3000${NC}"
  (cd "$FRONTEND_DIR" && npm run dev 2>&1 | sed "s/^/  [web] /") &
  FE_PID=$!
}

echo ""
echo -e "${BOLD}REFINET Cloud${NC} ${TEAL}Development${NC}"
echo -e "${DIM}─────────────────────────────────${NC}"

case "${1:-all}" in
  api)
    start_api
    ;;
  frontend|web|fe)
    start_frontend
    ;;
  all|*)
    start_api
    sleep 2
    start_frontend
    ;;
esac

echo ""
echo -e "${DIM}Press Ctrl+C to stop.${NC}"
echo ""

wait
