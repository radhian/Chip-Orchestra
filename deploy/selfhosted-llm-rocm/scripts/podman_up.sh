#!/usr/bin/env bash
# One-shot: create the bind-mount source dirs from the env file, then bring the
# stack up. This removes the "statfs .../workspaces: no such file or directory"
# footgun where prepare_host.sh is skipped before `podman-compose up`.
#
# Usage (pass the env file first, then the same -f compose args you'd use):
#   ./scripts/podman_up.sh r9700-core.rootless.env -f docker-compose.r9700-core.yml
#   ./scripts/podman_up.sh strix-agent.rootless.env \
#       -f docker-compose.strix-full.yml -f docker-compose.strix-full.rootless.yml
#
# Run under sudo for the rootful path:
#   sudo ./scripts/podman_up.sh r9700-core.env -f docker-compose.r9700-core.yml
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <env-file> -f <compose.yml> [-f <override.yml> ...] [extra up args]" >&2
  exit 1
fi

ENV_FILE="$1"; shift
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Preparing host dirs from ${ENV_FILE}"
"${SCRIPT_DIR}/prepare_host.sh" "${ENV_FILE}"

echo "==> podman-compose up"
exec podman-compose --env-file "${ENV_FILE}" "$@" up -d --build
