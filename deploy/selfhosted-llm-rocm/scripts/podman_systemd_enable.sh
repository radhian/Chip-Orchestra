#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Generate and enable systemd units for the running Chip Orchestra containers
# under Podman, so they auto-start on boot without a background daemon.
#
# Run as root ON EACH NODE after the stack is healthy:
#   sudo bash scripts/podman_systemd_enable.sh
#
# Match a subset with CONTAINER_FILTER (podman ps --filter name=...):
#   CONTAINER_FILTER=chip-orchestra sudo bash scripts/podman_systemd_enable.sh
# ---------------------------------------------------------------------------
set -euo pipefail

CONTAINER_FILTER="${CONTAINER_FILTER:-chip-orchestra}"
UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"

if ! command -v podman >/dev/null 2>&1; then
  echo "FAIL: podman not found" >&2
  exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "FAIL: run as root (sudo) so units land in ${UNIT_DIR}" >&2
  exit 1
fi

mapfile -t containers < <(podman ps --filter "name=${CONTAINER_FILTER}" --format '{{.Names}}')

if [ "${#containers[@]}" -eq 0 ]; then
  echo "No running containers match name=${CONTAINER_FILTER}."
  echo "Start the stacks first, then re-run this script."
  exit 1
fi

echo "Found ${#containers[@]} container(s):"
printf '  - %s\n' "${containers[@]}"
echo

cd "$UNIT_DIR"
for name in "${containers[@]}"; do
  echo "== $name =="
  podman generate systemd --files --name --restart-policy=always "$name"
  unit="container-${name}.service"
  systemctl daemon-reload
  systemctl enable --now "$unit"
  systemctl --no-pager --lines=0 status "$unit" || true
  echo
done

echo "Done. Units written to ${UNIT_DIR} and enabled."
echo "Tip: consider migrating to Quadlet (/etc/containers/systemd/*.container) later."
