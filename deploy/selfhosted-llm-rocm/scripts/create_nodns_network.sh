#!/usr/bin/env bash
# Create a rootless Podman network with DNS disabled, so netavark never starts
# aardvark-dns. This avoids the stuck 10.89.x.1:53 DNS-helper failure mode.
# Run from deploy/selfhosted-llm-rocm.
set -euo pipefail

ENV_FILE="${1:-strix-core.rootless.env}"
NETWORK="chip-orchestra-nodns"
SUBNET="10.90.0.0/24"
GATEWAY="10.90.0.1"

if [ -f "$ENV_FILE" ]; then
  parsed_network="$(awk -F= '/^PODMAN_NETWORK_NAME=/{print $2; exit}' "$ENV_FILE" | tr -d '[:space:]')"
  [ -n "$parsed_network" ] && NETWORK="$parsed_network"
fi

if podman network exists "$NETWORK"; then
  echo "[nodns] Network '$NETWORK' already exists. Inspecting..."
  podman network inspect "$NETWORK" | sed -n '1,120p'
  exit 0
fi

echo "[nodns] Creating rootless Podman network '$NETWORK' with DNS disabled..."
if podman network create --disable-dns --subnet "$SUBNET" --gateway "$GATEWAY" "$NETWORK" >/dev/null 2>&1; then
  :
else
  echo "[nodns] Fixed subnet create failed; retrying with Podman-assigned subnet..." >&2
  podman network create --disable-dns "$NETWORK" >/dev/null
fi

echo "[nodns] Created network '$NETWORK':"
podman network inspect "$NETWORK" | sed -n '1,160p'
