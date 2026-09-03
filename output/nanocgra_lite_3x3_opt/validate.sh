#!/bin/sh
# Reproducible package validation. Run from anywhere with UPRJ_ROOT set.
set -u
if [ -z "${UPRJ_ROOT:-}" ]; then
  echo "ERROR: UPRJ_ROOT must name the Chip-Orchestra repository root" >&2
  exit 2
fi
PKG="$UPRJ_ROOT/output/nanocgra_lite_3x3_opt"
export PKG
status=0
check() { if "$@"; then printf 'PASS: %s\n' "$*"; else printf 'FAIL: %s\n' "$*" >&2; status=1; fi; }

check python3 -m json.tool "$PKG/lvs_config.json"
check python3 "$PKG/scripts/validate_config.py" "$PKG/lvs_config.json"
check python3 "$PKG/gds/audit_canonical_gds.py" "$PKG/gds/nanocgra_lite_3x3_opt.gds"
check python3 "$PKG/pnr/check_d04_pg.py" "$PKG/pnr/nanocgra_lite_3x3_opt.def"
check python3 "$PKG/scripts/check_artifacts.py"
exit "$status"
