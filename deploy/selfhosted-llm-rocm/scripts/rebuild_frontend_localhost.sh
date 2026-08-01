#!/usr/bin/env bash
# Force-rebuild the static frontend bundle with VITE_API_BASE_URL=http://localhost:8080
# for SSH local-port-forward access (localhost:4173 + localhost:8080).
set -euo pipefail

ENV_FILE="${1:-strix-core.rootless.env}"
PROJECT="chip-orchestra-strix-single"
if [ -f "$ENV_FILE" ]; then
  parsed_project="$(awk -F= '/^COMPOSE_PROJECT_NAME=/{print $2; exit}' "$ENV_FILE" | tr -d '[:space:]')"
  [ -n "$parsed_project" ] && PROJECT="$parsed_project"
fi

# Ensure env file has the correct build-time Vite value. Do not source the file:
# it contains values with spaces.
if grep -q '^VITE_API_BASE_URL=' "$ENV_FILE"; then
  tmp="$(mktemp)"
  awk 'BEGIN{done=0} /^VITE_API_BASE_URL=/{print "VITE_API_BASE_URL=http://localhost:8080"; done=1; next} {print} END{if(!done) print "VITE_API_BASE_URL=http://localhost:8080"}' "$ENV_FILE" > "$tmp"
  mv "$tmp" "$ENV_FILE"
else
  printf '\nVITE_API_BASE_URL=http://localhost:8080\n' >> "$ENV_FILE"
fi

echo "[frontend] Removing stale frontend container/images..."
podman rm -f "${PROJECT}_frontend_1" 2>/dev/null || true
# Remove all likely frontend image tags produced by podman-compose/buildah.
podman images --format '{{.Repository}}:{{.Tag}} {{.ID}}' \
  | awk '/frontend/ {print $2}' \
  | sort -u \
  | xargs -r podman rmi -f 2>/dev/null || true

echo "[frontend] No-cache building frontend with localhost API base..."
podman-compose --env-file "$ENV_FILE" \
  -f docker-compose.r9700-core.yml \
  -f docker-compose.strix-agent.yml \
  -f docker-compose.strix-single-node.rootless.yml \
  build --no-cache frontend

echo "[frontend] Starting frontend..."
podman-compose --env-file "$ENV_FILE" \
  -f docker-compose.r9700-core.yml \
  -f docker-compose.strix-agent.yml \
  -f docker-compose.strix-single-node.rootless.yml \
  up -d frontend

echo "[frontend] Verifying served JS bundle does not contain the private LAN API URL..."
CID="$(podman ps --filter "name=${PROJECT}_frontend_1" --format '{{.ID}}' | head -n1)"
if [ -z "$CID" ]; then
  echo "[frontend] ERROR: frontend container is not running" >&2
  exit 1
fi

if podman exec "$CID" sh -lc 'grep -R "http://172.16.1.10:8080" -n /usr/share/nginx/html /app/dist 2>/dev/null'; then
  echo "[frontend] ERROR: stale bundle still contains http://172.16.1.10:8080" >&2
  exit 2
fi

podman exec "$CID" sh -lc 'grep -R "http://localhost:8080" -n /usr/share/nginx/html /app/dist 2>/dev/null | head -20' || true

echo "[frontend] OK: stale LAN URL not found. Hard-refresh http://localhost:4173 and retry login."
