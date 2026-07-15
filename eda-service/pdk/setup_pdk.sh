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

# The PDK build must match LibreLane's PINNED open_pdks revision — "latest"
# is not a valid volare version and the old call always failed, leaving
# PDK_ROOT empty and every hardening run without a GDS.
HASH="$(python3 -c "from librelane.common import get_pdk_hash; print(get_pdk_hash('$FAMILY'))" 2>/dev/null || true)"
if [ -z "$HASH" ]; then
  echo "[setup_pdk] could not resolve LibreLane's pinned PDK hash; skipping auto-setup."
  exit 0
fi

echo "[setup_pdk] Installing PDK family '$FAMILY' @ $HASH into $PDK_ROOT ..."
if command -v ciel >/dev/null 2>&1; then
  ciel enable --pdk-family "$FAMILY" --pdk-root "$PDK_ROOT" "$HASH" \
    && exit 0 || echo "[setup_pdk] ciel enable failed; trying volare."
fi
if command -v volare >/dev/null 2>&1; then
  volare enable --pdk "$FAMILY" --pdk-root "$PDK_ROOT" "$HASH" \
    || echo "[setup_pdk] volare enable failed; continuing without a prebuilt PDK."
fi
