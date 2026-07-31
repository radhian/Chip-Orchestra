#!/usr/bin/env bash
# Prepare an AMD host (R9700 or Strix Halo) for the Chip Orchestra Podman stack.
#
# Fixes the two first-run failures seen with Podman:
#   1. "statfs .../workspaces: no such file or directory"
#      -> Podman (unlike Docker) does not auto-create bind-mount source dirs.
#   2. "bind: cannot assign requested address" / "rootless netns: permission
#      denied" -> binding a fixed LAN IP (172.16.1.36:3306, ...) needs rootful
#      Podman, OR bind 0.0.0.0 and run rootless (see the rootless env file).
#
# Works both ways:
#   Rootful:   sudo ./scripts/prepare_host.sh
#   Rootless:  ./scripts/prepare_host.sh            (no sudo; workspace under $HOME)
#
# Override the workspace location with WORKSPACE_HOST_PATH=/abs/path
set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  MODE="rootful"
  WORKSPACE_HOST_PATH="${WORKSPACE_HOST_PATH:-/srv/chip-orchestra/workspaces}"
  ENV_HINT="r9700-core.env"
else
  MODE="rootless"
  WORKSPACE_HOST_PATH="${WORKSPACE_HOST_PATH:-${HOME}/chip-orchestra/workspaces}"
  ENV_HINT="r9700-core.rootless.env"
fi

echo "==> Mode: ${MODE}"
echo "==> Creating shared workspace: ${WORKSPACE_HOST_PATH}"
mkdir -p "${WORKSPACE_HOST_PATH}"
# World-writable so containerized services (which may run as remapped uids)
# can read/write generated artifacts. Tighten to a shared group if you prefer.
chmod 0777 "${WORKSPACE_HOST_PATH}" 2>/dev/null || true

# On the Strix Halo model host, also create the GGUF cache dir (set MODEL_DIR).
if [[ -n "${MODEL_DIR:-}" ]]; then
  echo "==> Creating model cache: ${MODEL_DIR}"
  mkdir -p "${MODEL_DIR}"
  chmod 0777 "${MODEL_DIR}" 2>/dev/null || true
fi

if command -v getenforce >/dev/null 2>&1 && [[ "$(getenforce)" != "Disabled" ]]; then
  echo "==> SELinux is $(getenforce): set WORKSPACE_MOUNT_FLAG=:z in your env file"
  if command -v chcon >/dev/null 2>&1; then
    chcon -Rt container_file_t "${WORKSPACE_HOST_PATH}" 2>/dev/null || true
  fi
fi

if [[ "${MODE}" == "rootless" ]]; then
  echo "==> Checking rootless prerequisites"
  command -v newuidmap >/dev/null 2>&1 || echo "WARN: 'newuidmap' missing (install uidmap) — rootless networking may fail"
  if ! grep -q "^$(id -un):" /etc/subuid 2>/dev/null; then
    echo "WARN: no subuid range for '$(id -un)' in /etc/subuid — ask an admin to run:"
    echo "      sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $(id -un)"
  fi
  # Clears a stale rootless network state that can cause the netns teardown error.
  podman system migrate >/dev/null 2>&1 || true
fi

if ! podman info >/dev/null 2>&1; then
  echo "WARN: 'podman info' failed — is Podman installed for this user?" >&2
fi

echo "==> Done. Next on this host:"
if [[ "${MODE}" == "rootless" ]]; then
  echo "    # edit WORKSPACE_HOST_PATH in ${ENV_HINT} to: ${WORKSPACE_HOST_PATH}"
  echo "    podman-compose --env-file ${ENV_HINT} -f docker-compose.r9700-core.yml up -d --build"
else
  echo "    sudo podman-compose --env-file ${ENV_HINT} -f docker-compose.r9700-core.yml up -d --build"
  echo
  echo "NOTE: images built earlier as a rootless user are NOT visible to rootful"
  echo "      Podman (separate storage). The --build above rebuilds them under root."
fi

