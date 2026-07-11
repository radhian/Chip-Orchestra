#!/usr/bin/env bash
# Auto-install the target open-source PDK via Volare if it is not already present.
#
# Controlled by:
#   PDK_ROOT  - install location (default /opt/pdk)
#   PDK       - PDK variant (default gf180mcuD; sky130A also supported)
# No-ops (exit 0) when the PDK already exists or Volare is unavailable, so the
# service still boots and the toolchain runners degrade gracefully.
set -uo pipefail

PDK_ROOT="${PDK_ROOT:-/opt/pdk}"
PDK="${PDK:-gf180mcuD}"

case "$PDK" in
  gf180*) FAMILY="gf180mcu" ;;
  sky130*) FAMILY="sky130" ;;
  *) FAMILY="$PDK" ;;
esac

mkdir -p "$PDK_ROOT"

if [ -d "$PDK_ROOT/$PDK" ] || [ -d "$PDK_ROOT/$FAMILY" ]; then
  echo "[setup_pdk] PDK '$PDK' already present under $PDK_ROOT; skipping."
  exit 0
fi

if ! command -v volare >/dev/null 2>&1; then
  echo "[setup_pdk] volare not installed; skipping auto-setup (set PDK_ROOT to a prepared PDK)."
  exit 0
fi

echo "[setup_pdk] Installing PDK family '$FAMILY' into $PDK_ROOT via Volare ..."
volare enable --pdk "$FAMILY" --pdk-root "$PDK_ROOT" latest \
  || echo "[setup_pdk] volare enable failed; continuing without a prebuilt PDK."
