#!/usr/bin/env bash
set -eu
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
export PATH=/home/wlmoi/venvs/librelane/bin:/home/wlmoi/.nix-profile/bin:/usr/bin:/bin
export PYTHONPATH="$REPO_DIR/paper/eda_runtime:$REPO_DIR/eda-service"
export PDK_ROOT="${PDK_ROOT:-/home/wlmoi/.volare}"
export QT_QPA_PLATFORM=offscreen
python "$SCRIPT_DIR/build_examples.py" "$@"
