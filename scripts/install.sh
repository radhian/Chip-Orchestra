#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Chip Orchestra — one-shot installer.
#
#   ./scripts/install.sh                  install everything + start the stack
#   ./scripts/install.sh --model <name>   use a different Ollama model
#                                         (default: glm-5.2:cloud)
#   ./scripts/install.sh --dev            also install frontend deps for
#                                         `npm run dev` (hot-reload mode)
#   ./scripts/install.sh --no-start       set up everything but don't start
#
# What it does:
#   1. Verifies (and where possible installs) Docker + Compose and Ollama.
#   2. Creates .env from .env.example and sets OLLAMA_MODEL.
#   3. Pulls the Ollama model if it isn't present.
#   4. Builds and starts the 6-container stack (MySQL, Redis, orchestrator,
#      agent, EDA, frontend) and waits until every service is healthy.
#
# After it finishes:  http://localhost:4173  (login admin / chip-orchestra)
# Start again later:  ./scripts/run.sh      Stop: ./scripts/run.sh stop
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODEL="glm-5.2:cloud"
MODEL_EXPLICIT=false
DEV=false
START=true
while [ $# -gt 0 ]; do
  case "$1" in
    --model)    MODEL="$2"; MODEL_EXPLICIT=true; shift 2 ;;
    --dev)      DEV=true; shift ;;
    --no-start) START=false; shift ;;
    -h|--help)  sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (see --help)"; exit 1 ;;
  esac
done

blue=$'\033[34m'; green=$'\033[32m'; yellow=$'\033[33m'; red=$'\033[31m'; reset=$'\033[0m'
log()  { echo "${blue}▶${reset} $*"; }
ok()   { echo "${green}✔${reset} $*"; }
warn() { echo "${yellow}⚠${reset} $*"; }
die()  { echo "${red}✘${reset} $*"; exit 1; }

# --- 1. Docker + Compose ----------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  warn "Docker not found."
  if [ "$(uname -s)" = "Linux" ]; then
    log "Installing Docker via get.docker.com (needs sudo)…"
    curl -fsSL https://get.docker.com | sudo sh || die "Docker install failed — install it manually: https://docs.docker.com/engine/install/"
    sudo usermod -aG docker "$USER" || true
    warn "Log out and back in (or run 'newgrp docker') so your user can use Docker, then re-run ./scripts/install.sh"
    exit 1
  else
    die "Install Docker Desktop first: https://docs.docker.com/get-docker/"
  fi
fi
docker ps >/dev/null 2>&1 || die "Docker is installed but not usable by this user. Start the Docker daemon and/or add yourself to the docker group: sudo usermod -aG docker \$USER && newgrp docker"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 plugin missing — https://docs.docker.com/compose/install/"
ok "Docker $(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1) + Compose ready"

# --- 2. Ollama ---------------------------------------------------------------
if ! command -v ollama >/dev/null 2>&1; then
  log "Installing Ollama…"
  curl -fsSL https://ollama.com/install.sh | sh || die "Ollama install failed — https://ollama.com/download"
fi
if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
  log "Starting Ollama server…"
  (sudo -n systemctl start ollama 2>/dev/null) || (nohup ollama serve >/dev/null 2>&1 &)
  for i in $(seq 1 15); do
    curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
    [ "$i" = 15 ] && die "Ollama server did not come up on :11434 — run 'ollama serve' manually and re-run ./scripts/install.sh"
  done
fi
ok "Ollama server running"

# --- 2b. Make Ollama reachable from Docker containers ------------------------
# The agent-service container calls Ollama via host.docker.internal. Ollama's
# default systemd unit binds 127.0.0.1 only, which containers cannot reach.
OLLAMA_DOCKER_URL="http://host.docker.internal:11434"
if command -v ss >/dev/null 2>&1 \
   && ss -tln 2>/dev/null | grep -q '127\.0\.0\.1:11434' \
   && ! ss -tln 2>/dev/null | grep -qE '(0\.0\.0\.0|\[::\]|\*):11434'; then
  warn "Ollama listens on 127.0.0.1 only — Docker containers cannot reach it."
  if systemctl is-active ollama >/dev/null 2>&1 && sudo -v 2>/dev/null; then
    log "Setting OLLAMA_HOST=0.0.0.0 via systemd override (sudo)…"
    sudo mkdir -p /etc/systemd/system/ollama.service.d
    printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"\n' | sudo tee /etc/systemd/system/ollama.service.d/docker-access.conf >/dev/null
    sudo systemctl daemon-reload && sudo systemctl restart ollama
    for i in $(seq 1 15); do
      curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1 && break; sleep 1
    done
    ok "Ollama now listens on all interfaces"
  else
    log "No sudo — starting unprivileged forwarder on :11435 instead…"
    if ! pgrep -f "ollama-docker-proxy.py" >/dev/null 2>&1; then
      nohup python3 "$ROOT/scripts/ollama-docker-proxy.py" >/dev/null 2>&1 &
      sleep 1
    fi
    OLLAMA_DOCKER_URL="http://host.docker.internal:11435"
    warn "Forwarder does not survive reboots. Permanent fix: sudo systemctl edit ollama → [Service] Environment=\"OLLAMA_HOST=0.0.0.0\""
  fi
fi

# --- 3. Model ----------------------------------------------------------------
if ! ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$MODEL"; then
  log "Pulling Ollama model $MODEL…"
  if ! ollama pull "$MODEL"; then
    case "$MODEL" in
      *:cloud) die "Pull failed. '$MODEL' is an Ollama *cloud* model — run 'ollama signin' once, then re-run ./scripts/install.sh" ;;
      *)       die "Pull failed for '$MODEL'. Pick any model from https://ollama.com/library and re-run with --model <name>" ;;
    esac
  fi
fi
ok "Model $MODEL available"

# --- 4. .env ------------------------------------------------------------------
ENV_CREATED=false
if [ ! -f .env ]; then
  cp .env.example .env
  ENV_CREATED=true
  ok "Created .env from .env.example"
fi
# Only (re)write OLLAMA_MODEL when the user asked for a model explicitly or the
# .env was just created — a re-run must never clobber the user's chosen model.
if $MODEL_EXPLICIT || $ENV_CREATED; then
  if grep -q '^OLLAMA_MODEL=' .env; then
    sed -i.bak "s|^OLLAMA_MODEL=.*|OLLAMA_MODEL=$MODEL|" .env && rm -f .env.bak
  else
    printf '\nOLLAMA_MODEL=%s\n' "$MODEL" >> .env
  fi
else
  MODEL="$(grep -E '^OLLAMA_MODEL=' .env | tail -1 | cut -d= -f2-)"
  MODEL="${MODEL:-glm-5.2:cloud}"
fi
if grep -q '^OLLAMA_BASE_URL=' .env; then
  sed -i.bak "s|^OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL=$OLLAMA_DOCKER_URL|" .env && rm -f .env.bak
else
  printf 'OLLAMA_BASE_URL=%s\n' "$OLLAMA_DOCKER_URL" >> .env
fi
ok ".env configured (LLM: ollama / $MODEL via $OLLAMA_DOCKER_URL)"

# --- 5. Optional: frontend deps for hot-reload dev ---------------------------
if $DEV; then
  command -v node >/dev/null 2>&1 || die "--dev needs Node.js >= 18: https://nodejs.org"
  log "Installing frontend dependencies (npm)…"
  ( cd frontend && npm install --no-audit --no-fund )
  [ -f frontend/.env ] || cp frontend/.env.example frontend/.env
  ok "Frontend dev mode ready — run: cd frontend && npm run dev  (http://localhost:5173)"
fi

$START || { ok "Setup complete (stack not started — run ./scripts/run.sh)"; exit 0; }

# --- 6. Build + start the stack ----------------------------------------------
log "Building and starting the stack (first build can take several minutes)…"
docker compose up -d --build

# --- 7. Wait for health --------------------------------------------------------
wait_http() { # name url tries
  local name="$1" url="$2" tries="${3:-60}"
  for i in $(seq 1 "$tries"); do
    if curl -fsS "$url" >/dev/null 2>&1; then ok "$name healthy"; return 0; fi
    sleep 5
  done
  warn "$name not responding at $url — check: docker compose logs ${name}"
  return 1
}
FAIL=0
wait_http orchestrator-service "http://localhost:${OPERATOR_PORT:-8080}/health" || FAIL=1
wait_http agent-service        "http://localhost:${AGENT_PORT:-8001}/health"    || FAIL=1
wait_http eda-service          "http://localhost:${EDA_PORT:-8002}/health"      || FAIL=1
wait_http frontend             "http://localhost:${FRONTEND_PORT:-4173}"        || FAIL=1
[ "$FAIL" = 0 ] || die "Some services failed to come up — see messages above."

echo
echo "${green}Chip Orchestra is up.${reset}"
echo "  • Frontend      →  http://localhost:${FRONTEND_PORT:-4173}"
echo "  • Orchestrator  →  http://localhost:${OPERATOR_PORT:-8080}"
echo "  • Agent Service →  http://localhost:${AGENT_PORT:-8001}"
echo "  • EDA Service   →  http://localhost:${EDA_PORT:-8002}"
echo "  • Login         →  admin / chip-orchestra"
echo "  • LLM           →  ollama / $MODEL"
echo
echo "Stop the stack:  ./scripts/run.sh stop"
