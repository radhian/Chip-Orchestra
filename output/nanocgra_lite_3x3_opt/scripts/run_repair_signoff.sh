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
"$OPENROAD_BIN" -exit -no_init "$PKG/pnr/finalize_odb.tcl" > "$PKG/logs/finalize_odb.log" 2>&1
"$KLAYOUT_BIN" -zz -b -r "$PKG/gds/def2gds.py" \
  -rd def_file="$PKG/pnr/nanocgra_lite_3x3_opt.def" \
  -rd out_gds="$PKG/gds/nanocgra_lite_3x3_opt.gds" \
  -rd map_file="$PDK_ROOT/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map" \
  -rd tech_lef="$PKG/pnr/gf180mcu_fd_sc_mcu7t5v0__drc_clean.tlef" \
  -rd cell_lef="$SCDIR/lef/gf180mcu_fd_sc_mcu7t5v0.lef" \
  -rd cell_gds="$SCDIR/gds/gf180mcu_fd_sc_mcu7t5v0.gds" \
  -rd top_name=NanoCGRA_Lite > "$PKG/logs/def2gds_repair.log" 2>&1
python3 "$PKG/gds/audit_canonical_gds.py" "$PKG/gds/nanocgra_lite_3x3_opt.gds"
DRC_DIR="$PKG/reports/signoff/foundry_drc_full"
rm -rf "$DRC_DIR"
python3 "$PDK_ROOT/gf180mcuD/libs.tech/klayout/drc/run_drc.py" \
  --path="$PKG/gds/nanocgra_lite_3x3_opt.gds" \
  --variant=C --topcell=NanoCGRA_Lite --run_mode=flat --mp=12 \
  --run_dir="$DRC_DIR" > "$PKG/reports/signoff/foundry_drc_full.log" 2>&1
python3 - "$DRC_DIR" <<'PY'
import glob
import os
import sys
import xml.etree.ElementTree as ET

report_dir = sys.argv[1]
reports = glob.glob(os.path.join(report_dir, "*.lyrdb"))
if len(reports) < 50:
    raise SystemExit(f"foundry DRC is incomplete: only {len(reports)} rule-table reports")
violations = []
for report in reports:
    items = ET.parse(report).getroot().find("items")
    count = len(items) if items is not None else 0
    if count:
        violations.append((os.path.basename(report), count))
if violations:
    raise SystemExit(f"foundry DRC is not clean: {violations}")
print(f"PASS: {len(reports)} foundry GF180 variant-C rule tables have zero DRC items")
PY
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
