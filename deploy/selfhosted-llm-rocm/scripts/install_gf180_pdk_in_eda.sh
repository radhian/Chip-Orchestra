#!/usr/bin/env bash
# Install/repair the GF180MCU PDK inside the running eda-service container's
# mounted PDK_ROOT volume. Designed for rootless Podman + podman-compose.
set -euo pipefail

ENV_FILE="${1:-strix-core.rootless.env}"
PROJECT="chip-orchestra-strix-single"
SERVICE="eda-service"
CONTAINER="${PROJECT}_${SERVICE}_1"

if [ -f "$ENV_FILE" ]; then
  # COMPOSE_PROJECT_NAME is safe to parse without sourcing the whole env file
  # (some values contain spaces and are intentionally unquoted).
  parsed_project="$(awk -F= '/^COMPOSE_PROJECT_NAME=/{print $2; exit}' "$ENV_FILE" | tr -d '[:space:]')"
  if [ -n "$parsed_project" ]; then
    PROJECT="$parsed_project"
    CONTAINER="${PROJECT}_${SERVICE}_1"
  fi
fi

if ! podman container exists "$CONTAINER"; then
  echo "[pdk] Container '$CONTAINER' not found. Current eda-service containers:" >&2
  podman ps -a --format '  {{.Names}}\t{{.Status}}' | grep eda-service || true
  exit 1
fi

echo "[pdk] Target container: $CONTAINER"

echo "[pdk] Current PDK env and /opt/pdk contents:"
podman exec "$CONTAINER" sh -lc 'echo "PDK_ROOT=${PDK_ROOT:-/opt/pdk}"; echo "PDK=${PDK:-gf180mcuD}"; ls -la "${PDK_ROOT:-/opt/pdk}" || true'

echo "[pdk] Running bundled setup_pdk.sh..."
podman exec "$CONTAINER" bash -lc 'set -euo pipefail; chmod +x /app/pdk/setup_pdk.sh 2>/dev/null || true; /app/pdk/setup_pdk.sh'

echo "[pdk] Verifying LibreLane-visible PDK layout..."
podman exec "$CONTAINER" bash -lc '
  set -euo pipefail
  PDK_ROOT="${PDK_ROOT:-/opt/pdk}"
  PDK="${PDK:-gf180mcuD}"
  echo "PDK_ROOT=$PDK_ROOT"
  echo "PDK=$PDK"
  find "$PDK_ROOT" -maxdepth 3 -type d | sort | sed -n "1,120p"
  test -f "$PDK_ROOT/$PDK/libs.tech/openlane/config.tcl"
  test -d "$PDK_ROOT/$PDK/libs.ref"
  python3 - <<PY
from librelane.common import get_pdk_hash
print("LibreLane pinned gf180mcu hash:", get_pdk_hash("gf180mcu"))
PY
'

echo "[pdk] OK: $CONTAINER can see gf180mcuD under PDK_ROOT. Retry the PNR stage."
