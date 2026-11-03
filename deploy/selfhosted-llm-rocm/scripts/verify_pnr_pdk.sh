#!/usr/bin/env bash
# Verify the exact PDK path that the PNR/LibreLane runner uses inside eda-service.
set -euo pipefail

ENV_FILE="${1:-strix-core.rootless.env}"
PROJECT="chip-orchestra-strix-single"
if [ -f "$ENV_FILE" ]; then
  parsed_project="$(awk -F= '/^COMPOSE_PROJECT_NAME=/{print $2; exit}' "$ENV_FILE" | tr -d '[:space:]')"
  [ -n "$parsed_project" ] && PROJECT="$parsed_project"
fi
CONTAINER="${PROJECT}_eda-service_1"

if ! podman container exists "$CONTAINER"; then
  echo "[verify] Container '$CONTAINER' not found" >&2
  exit 1
fi

podman exec "$CONTAINER" bash -lc '
  set -euo pipefail
  PDK_ROOT="${PDK_ROOT:-/opt/pdk}"
  PDK="${PDK:-gf180mcuD}"
  CONFIG="$PDK_ROOT/$PDK/libs.tech/openlane/config.tcl"
  echo "container=$(hostname)"
  echo "PDK_ROOT=$PDK_ROOT"
  echo "PDK=$PDK"
  echo "PDK_VERSION=${PDK_VERSION:-unset}"
  echo "LibreLane command would use: librelane --manual-pdk --pdk-root $PDK_ROOT config.json"
  echo "Expected config: $CONFIG"
  echo "--- /etc/resolv.conf"; cat /etc/resolv.conf || true
  echo "--- /opt/pdk snapshot"; find "$PDK_ROOT" -maxdepth 4 -type d | sort | sed -n "1,160p" || true
  if [ -f "$CONFIG" ]; then
    echo "PNR_PDK_OK"
  else
    echo "PNR_PDK_MISSING"
    exit 2
  fi
'
