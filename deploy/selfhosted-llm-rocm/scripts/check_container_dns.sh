#!/usr/bin/env bash
# Diagnose outbound DNS from the rootless Podman containers used by the Strix
# single-node stack. This checks /etc/resolv.conf plus real external lookups.
set -euo pipefail

PROJECT="chip-orchestra-strix-single"
ENV_FILE="${1:-strix-core.rootless.env}"
if [ -f "$ENV_FILE" ]; then
  parsed_project="$(awk -F= '/^COMPOSE_PROJECT_NAME=/{print $2; exit}' "$ENV_FILE" | tr -d '[:space:]')"
  [ -n "$parsed_project" ] && PROJECT="$parsed_project"
fi

for svc in eda-service orchestrator-service agent-service; do
  c="${PROJECT}_${svc}_1"
  if ! podman container exists "$c"; then
    echo "== $c: missing =="
    continue
  fi
  echo "== $c =="
  podman exec "$c" sh -lc '
    echo "--- /etc/resolv.conf"; cat /etc/resolv.conf || true
    echo "--- hosts"; getent hosts github.com || true; getent hosts google.com || true
    echo "--- HTTP probe"; python3 - <<PY
import urllib.request
for url in ("https://github.com", "https://google.com"):
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            print(url, r.status)
    except Exception as e:
        print(url, type(e).__name__, e)
PY
  '
  echo
done
