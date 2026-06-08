#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Chip Orchestra — run the whole stack (agentic backend + frontend) together.
#
#   ./run.sh            start backend + frontend (installs deps on first run)
#   ./run.sh --setup    force-reinstall backend + frontend dependencies
#
# Backend : http://localhost:8000   (API docs at /docs)
# Frontend: http://localhost:5173
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
SETUP=false
[ "${1:-}" = "--setup" ] && SETUP=true

c_blue=$'\033[34m'; c_green=$'\033[32m'; c_yellow=$'\033[33m'; c_reset=$'\033[0m'
log() { echo "${c_blue}▶${c_reset} $*"; }

# --- prerequisites ---------------------------------------------------------
command -v uv   >/dev/null || { echo "uv is required (https://docs.astral.sh/uv/)"; exit 1; }
command -v node >/dev/null || { echo "node is required"; exit 1; }

# --- backend setup ---------------------------------------------------------
cd "$BACKEND"
if [ ! -d .venv ] || $SETUP; then
  log "Backend: creating venv + installing dependencies (uv)…"
  uv venv --python 3.12
  uv pip install -e .
fi
[ -f .env ] || { cp .env.example .env; log "Backend: created .env from .env.example"; }

# --- durable infra: Postgres + MinIO via Docker (optional) -----------------
# Brings up the local Postgres + object storage so chip runs auto-persist.
# Skip with NO_DOCKER=1 (the backend then falls back to the local file store).
if [ "${NO_DOCKER:-0}" != "1" ] && grep -q '^DATABASE_URL=' "$BACKEND/.env" 2>/dev/null; then
  if command -v docker >/dev/null 2>&1 && docker ps >/dev/null 2>&1; then
    log "Infra: starting Postgres + MinIO (docker compose)…"
    ( cd "$ROOT" && docker compose up -d ) >/dev/null 2>&1 || log "Infra: docker compose failed — backend will use the local file store"
  else
    echo "${c_yellow}⚠ Docker not available — Postgres/MinIO skipped; using the local file store.${c_reset}"
  fi
fi

# --- frontend setup --------------------------------------------------------
cd "$FRONTEND"
if [ ! -f .env ]; then
  printf 'VITE_API_BASE_URL=http://localhost:%s\nVITE_USE_MOCKS=true\n' "$BACKEND_PORT" > .env
  log "Frontend: created .env"
fi
if [ ! -x node_modules/.bin/vite ] || $SETUP; then
  if command -v npm >/dev/null 2>&1; then
    log "Frontend: installing dependencies (npm)…"
    npm install --no-audit --no-fund
  elif command -v pnpm >/dev/null 2>&1; then
    log "Frontend: installing dependencies (pnpm)…"
    pnpm install --ignore-workspace
  fi
fi

# --- soft check: is Ollama reachable? --------------------------------------
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
if ! curl -s "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
  echo "${c_yellow}⚠ Ollama not reachable at ${OLLAMA_HOST} — RTL generation will fail until 'ollama serve' is running.${c_reset}"
fi

# --- run both with shared lifecycle ----------------------------------------
pids=()
cleanup() {
  echo
  log "Shutting down…"
  for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

log "Starting backend on http://localhost:${BACKEND_PORT}"
( cd "$BACKEND" && exec uv run uvicorn chip_orchestra_backend.main:app \
    --host "$BACKEND_HOST" --port "$BACKEND_PORT" ) &
pids+=($!)

log "Starting frontend on http://localhost:${FRONTEND_PORT}"
( cd "$FRONTEND" && exec node_modules/.bin/vite --host --port "$FRONTEND_PORT" --strictPort ) &
pids+=($!)

echo
echo "${c_green}Chip Orchestra is up:${c_reset}"
echo "  • Frontend  →  http://localhost:${FRONTEND_PORT}"
echo "  • Backend   →  http://localhost:${BACKEND_PORT}  (docs: /docs)"
echo "  Press Ctrl+C to stop both."
echo

wait
