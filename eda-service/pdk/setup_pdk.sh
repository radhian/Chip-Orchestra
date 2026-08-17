#!/usr/bin/env bash
# Auto-install the target open-source PDK via Volare if it is not already present.
#
# Controlled by:
#   PDK_ROOT  - install location (default /opt/pdk)
#   PDK       - PDK variant (default gf180mcuD; sky130A also supported)
#   PDK_SETUP_REQUIRED - 1/true (default) fails if setup cannot verify the PDK;
#                        0/false only warns, useful for SIM-only images.
set -euo pipefail

PDK_ROOT="${PDK_ROOT:-/opt/pdk}"
PDK="${PDK:-gf180mcuD}"
# LibreLane's pinned open_pdks commit can point at a PDK build that is not
# published in Volare for gf180mcu. Use a known published gf180mcu build by
# default, but allow deployments to override it.
PDK_VERSION="${PDK_VERSION:-c6d73a35f524070e85faff4a6a9eef49553ebc2b}"
REQUIRED="${PDK_SETUP_REQUIRED:-1}"

case "$PDK" in
  gf180*) FAMILY="gf180mcu" ;;
  sky130*) FAMILY="sky130" ;;
  *) FAMILY="$PDK" ;;
esac

warn_or_fail() {
  echo "[setup_pdk] ERROR: $*" >&2
  case "$REQUIRED" in
    0|false|False|FALSE|no|No|NO) return 0 ;;
    *) return 1 ;;
  esac
}

verify_pdk() {
  local root="$1"
  local pdk="$2"
  test -f "$root/$pdk/libs.tech/openlane/config.tcl" || return 1
  test -d "$root/$pdk/libs.ref" || return 1
}

mkdir -p "$PDK_ROOT"

if verify_pdk "$PDK_ROOT" "$PDK"; then
  echo "[setup_pdk] PDK '$PDK' already present and LibreLane-visible under $PDK_ROOT; skipping."
  exit 0
fi

if [ -d "$PDK_ROOT/$PDK" ]; then
  echo "[setup_pdk] Found $PDK_ROOT/$PDK, but required LibreLane files are missing. Re-running setup."
fi

# Volare uses PDK families (gf180mcu/sky130), while LibreLane config uses
# variants (gf180mcuD/sky130A). PDK_VERSION must be a version that exists in
# `volare ls-remote --pdk "$FAMILY"`.
HASH="$PDK_VERSION"
if [ -z "$HASH" ]; then
  warn_or_fail "PDK_VERSION is empty for family '$FAMILY'."
  exit $?
fi

echo "[setup_pdk] Installing PDK family '$FAMILY' @ $HASH into $PDK_ROOT ..."
if command -v volare >/dev/null 2>&1; then
  volare enable --pdk "$FAMILY" --pdk-root "$PDK_ROOT" "$HASH"
elif command -v ciel >/dev/null 2>&1; then
  ciel enable --pdk-family "$FAMILY" --pdk-root "$PDK_ROOT" "$HASH"
else
  warn_or_fail "neither volare nor ciel is installed in the image."
  exit $?
fi

if verify_pdk "$PDK_ROOT" "$PDK"; then
  echo "[setup_pdk] OK: '$PDK' is installed and LibreLane-visible at $PDK_ROOT/$PDK."
  exit 0
fi

echo "[setup_pdk] Directory snapshot after attempted install:" >&2
find "$PDK_ROOT" -maxdepth 3 -type d | sort | sed -n '1,120p' >&2 || true
warn_or_fail "'$PDK' is still not LibreLane-visible. Expected $PDK_ROOT/$PDK/libs.tech/openlane/config.tcl."
