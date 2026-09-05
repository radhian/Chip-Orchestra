#!/bin/sh
set -eu
: "${UPRJ_ROOT:?set UPRJ_ROOT to the Chip-Orchestra repository root}"
: "${PDK_ROOT:?set PDK_ROOT to the directory containing gf180mcuD}"
OPENROAD_BIN=${OPENROAD_BIN:-openroad}
KLAYOUT_BIN=${KLAYOUT_BIN:-klayout}
MAGIC_BIN=${MAGIC_BIN:-magic}
NETGEN_BIN=${NETGEN_BIN:-netgen}
PKG="$UPRJ_ROOT/output/nanocgra_lite_3x3_opt"
SCDIR="$PDK_ROOT/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0"

"$OPENROAD_BIN" -exit -no_init "$PKG/pnr/flow.tcl" > "$PKG/logs/pnr_repair.log" 2>&1
"$KLAYOUT_BIN" -zz -b -r "$PKG/gds/def2gds.py" \
  -rd def_file="$PKG/pnr/nanocgra_lite_3x3_opt.def" \
  -rd out_gds="$PKG/gds/nanocgra_lite_3x3_opt.gds" \
  -rd map_file="$PDK_ROOT/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map" \
  -rd tech_lef="$SCDIR/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef" \
  -rd cell_lef="$SCDIR/lef/gf180mcu_fd_sc_mcu7t5v0.lef" \
  -rd cell_gds="$SCDIR/gds/gf180mcu_fd_sc_mcu7t5v0.gds" \
  -rd top_name=NanoCGRA_Lite > "$PKG/logs/def2gds_repair.log" 2>&1
python3 "$PKG/gds/audit_canonical_gds.py" "$PKG/gds/nanocgra_lite_3x3_opt.gds"
for mode in flat deep; do
  report="$PKG/reports/signoff/drc_full_${mode}.lyrdb"
  log="$PKG/reports/signoff/drc_full_${mode}.log"
  mode_arg=""
  if [ "$mode" = deep ]; then mode_arg="-rd run_mode=deep"; fi
  # shellcheck disable=SC2086
  "$KLAYOUT_BIN" -zz -b \
    -r "$PDK_ROOT/gf180mcuD/libs.tech/klayout/drc/rule_decks/main.drc" \
    -rd input="$PKG/gds/nanocgra_lite_3x3_opt.gds" \
    -rd report="$report" \
    -rd topcell=NanoCGRA_Lite \
    -rd feol=true -rd beol=true -rd conn_drc=true \
    -rd metal_top=9K -rd metal_level=5LM $mode_arg > "$log" 2>&1
  python3 - "$report" "$log" <<'PY'
import sys
import xml.etree.ElementTree as ET
report, log = sys.argv[1:]
text = open(log, errors="replace").read()
for required in ("FEOL enabled: true", "BEOL enabled: true", "CONNECTIVITY_RULES enabled: true"):
    if required not in text:
        raise SystemExit(f"full DRC configuration missing: {required}")
items = ET.parse(report).getroot().find("items")
if items is None or len(items):
    raise SystemExit(f"full DRC is not clean: {len(items) if items is not None else 'missing items section'}")
print(f"PASS: {report} has zero full FEOL/BEOL DRC items")
PY
done
"$OPENROAD_BIN" -exit -no_init "$PKG/reports/signoff/sta_ss.tcl" > "$PKG/reports/signoff/sta_ss_repair.rpt" 2>&1
"$OPENROAD_BIN" -exit -no_init "$PKG/reports/signoff/pg_connectivity.tcl" > "$PKG/reports/signoff/pg_connectivity.rpt" 2>&1
"$OPENROAD_BIN" -exit -no_init "$PKG/reports/pdnsim_ir.tcl" > "$PKG/reports/pdnsim.log" 2>&1
"$MAGIC_BIN" -dnull -noconsole \
  -rcfile "$PDK_ROOT/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc" \
  "$PKG/reports/lvs/extract_gds.tcl" > "$PKG/reports/lvs/magic_gds_extract_repair.log" 2>&1
rm -f "$PKG"/reports/lvs/*.ext
"$NETGEN_BIN" -batch source "$PKG/reports/lvs/run_lvs_final.tcl" > "$PKG/reports/lvs/netgen_final.log" 2>&1
if [ ! -s "$PKG/reports/lvs/netgen.complete" ]; then
  echo "ERROR: real transistor-level LVS did not pass" >&2
  exit 1
fi
"$PKG/validate.sh"
