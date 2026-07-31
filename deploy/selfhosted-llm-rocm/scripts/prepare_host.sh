#!/usr/bin/env bash
# Prepare an AMD host (R9700 or Strix Halo) for the Chip Orchestra Podman stack.
#
# Fixes the two first-run failures seen with rootless Podman:
#   1. "statfs /srv/chip-orchestra/workspaces: no such file or directory"
#      -> Podman (unlike Docker) does not auto-create bind-mount source dirs.
#   2. "bind: cannot assign requested address" / "rootless netns: permission
#      denied" -> binding a fixed LAN IP (172.16.1.36:3306, ...) needs rootful
#      Podman. This script must therefore be run with sudo.
#
# Usage:
#   sudo ./scripts/prepare_host.sh
#   sudo WORKSPACE_HOST_PATH=/mnt/nfs/chip-orchestra/workspaces ./scripts/prepare_host.sh
set -euo pipefail

WORKSPACE_HOST_PATH="${WORKSPACE_HOST_PATH:-/srv/chip-orchestra/workspaces}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run with sudo (rootful Podman is required to bind the LAN IP)." >&2
  echo "       sudo $0" >&2
  exit 1
fi

echo "==> Creating shared workspace: ${WORKSPACE_HOST_PATH}"
mkdir -p "${WORKSPACE_HOST_PATH}"
# World-writable so the containerized services (which may run as non-root uids)
# can read/write generated artifacts. Tighten to a shared group if you prefer.
chmod 0777 "${WORKSPACE_HOST_PATH}"

if command -v getenforce >/dev/null 2>&1 && [[ "$(getenforce)" != "Disabled" ]]; then
  echo "==> SELinux is $(getenforce): remember to set WORKSPACE_MOUNT_FLAG=:z in your env file"
  if command -v chcon >/dev/null 2>&1; then
    chcon -Rt container_file_t "${WORKSPACE_HOST_PATH}" 2>/dev/null || true
  fi
fi

echo "==> Checking Podman registries (short-name resolution)"
if ! podman info >/dev/null 2>&1; then
  echo "WARN: 'podman info' failed under root; is Podman installed for root?" >&2
fi

echo "==> Done. Next (as root, on this host):"
echo "    sudo podman-compose --env-file r9700-core.env -f docker-compose.r9700-core.yml up -d --build"
echo
echo "NOTE: images you may have built earlier as a rootless user are NOT visible"
echo "      to rootful Podman (separate storage). The --build above rebuilds them"
echo "      under root storage, which is expected."
