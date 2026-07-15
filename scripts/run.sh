#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Chip Orchestra — daily driver. Starts/stops the ALREADY-INSTALLED stack.
#
#   ./scripts/run.sh            start the stack and print the web link
#   ./scripts/run.sh stop       stop the stack
#   ./scripts/run.sh restart    stop + start
#   ./scripts/run.sh --build    start and rebuild images (after a code change)
#
# run.sh NEVER reinstalls, never asks for sudo, and never rewrites your .env.
# First-time setup (Docker/Ollama install, model pull, .env creation) is
# ./scripts/install.sh — run that once, then use run.sh day-to-day.
# ---------------------------------------------------------------------------
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

blue=$'\033[34m'; green=$'\033[32m'; yellow=$'\033[33m'; red=$'\033[31m'; reset=$'\033[0m'
log()  { echo "${blue}▶${reset} $*"; }
ok()   { echo "${green}✔${reset} $*"; }
warn() { echo "${yellow}⚠${reset} $*"; }
die()  { echo "${red}✘${reset} $*"; exit 1; }

# read a KEY=value from .env (without sourcing arbitrary content)
envval() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' ; }

BUILD=false
CMD="start"
while [ $# -gt 0 ]; do
  case "$1" in
    stop)      CMD="stop"; shift ;;
    restart)   CMD="restart"; shift ;;
    start)     CMD="start"; shift ;;
    --build)   BUILD=true; shift ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) die "Unknown option: $1 (see --help). For installation use ./scripts/install.sh" ;;
  esac
done

if [ "$CMD" = "stop" ] || [ "$CMD" = "restart" ]; then
  docker compose down
  echo "Chip Orchestra stack stopped."
  [ "$CMD" = "stop" ] && exit 0
fi

# --- sanity: installed? -------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "Docker not found — run ./scripts/install.sh first."
docker ps >/dev/null 2>&1 || die "Docker daemon not usable — start Docker (or run ./scripts/install.sh)."
[ -f .env ] || die "No .env found — run ./scripts/install.sh once to set everything up."

FRONTEND_PORT="$(envval FRONTEND_PORT)"; FRONTEND_PORT="${FRONTEND_PORT:-4173}"
OPERATOR_PORT="$(envval OPERATOR_PORT)"; OPERATOR_PORT="${OPERATOR_PORT:-8080}"
AGENT_PORT="$(envval AGENT_PORT)";       AGENT_PORT="${AGENT_PORT:-8001}"
EDA_PORT="$(envval EDA_PORT)";           EDA_PORT="${EDA_PORT:-8002}"
MODEL="$(envval OLLAMA_MODEL)";          MODEL="${MODEL:-?}"
PROVIDER="$(envval LLM_PROVIDER)";       PROVIDER="${PROVIDER:-ollama}"
BASE_URL="$(envval OLLAMA_BASE_URL)"

# --- self-heal Ollama after a reboot (no sudo, no .env changes) ---------------
if [ "$PROVIDER" = "ollama" ]; then
  if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
    log "Ollama server not running — starting it…"
    (sudo -n systemctl start ollama 2>/dev/null) || (nohup ollama serve >/dev/null 2>&1 &)
    for i in $(seq 1 15); do
      curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1 && break; sleep 1
    done
    curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1 \
      && ok "Ollama server running" \
      || warn "Ollama did not come up on :11434 — LLM stages will fall back. Run 'ollama serve' or ./scripts/install.sh"
  fi
  # .env points at the unprivileged :11435 forwarder → make sure it's alive
  case "$BASE_URL" in *:11435*)
    if ! pgrep -f "ollama-docker-proxy.py" >/dev/null 2>&1; then
      log "Restarting the Ollama Docker forwarder on :11435…"
      nohup python3 "$ROOT/scripts/ollama-docker-proxy.py" >/dev/null 2>&1 &
      sleep 1
    fi ;;
  esac
fi

# --- start ---------------------------------------------------------------------
if $BUILD; then
  log "Starting the stack (rebuilding images)…"
  docker compose up -d --build
else
  log "Starting the stack…"
  docker compose up -d
fi

echo
echo "${green}Chip Orchestra is starting.${reset}"
echo "  • Web UI        →  ${green}http://localhost:${FRONTEND_PORT}${reset}   (login admin / chip-orchestra)"
echo "  • Orchestrator  →  http://localhost:${OPERATOR_PORT}"
echo "  • Agent Service →  http://localhost:${AGENT_PORT}"
echo "  • EDA Service   →  http://localhost:${EDA_PORT}"
echo "  • LLM           →  ${PROVIDER} / ${MODEL}"
echo

# --- wait for health -------------------------------------------------------------
wait_http() { # name url tries
  local name="$1" url="$2" tries="${3:-60}"
  for i in $(seq 1 "$tries"); do
    if curl -fsS "$url" >/dev/null 2>&1; then ok "$name healthy"; return 0; fi
    sleep 5
  done
  warn "$name not responding at $url — check: docker compose logs $name"
  return 1
}
FAIL=0
wait_http orchestrator-service "http://localhost:${OPERATOR_PORT}/health" || FAIL=1
wait_http agent-service        "http://localhost:${AGENT_PORT}/health"    || FAIL=1
wait_http eda-service          "http://localhost:${EDA_PORT}/health"      || FAIL=1
wait_http frontend             "http://localhost:${FRONTEND_PORT}"        || FAIL=1
[ "$FAIL" = 0 ] || die "Some services failed to come up — see messages above."

echo
echo "${green}All services healthy → open http://localhost:${FRONTEND_PORT}${reset}"
echo "Stop the stack:  ./scripts/run.sh stop"
