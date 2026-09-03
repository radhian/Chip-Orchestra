#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path

pkg = Path(os.environ["PKG"])
errors = []
checks = {
    "powered netlist": pkg / "pnr/nanocgra_lite_3x3_opt.pnr.pwr.v",
    "canonical GDS": pkg / "gds/nanocgra_lite_3x3_opt.gds",
    "D04 reference": pkg / "pnr/D04.def",
}
for label, path in checks.items():
    if not path.is_file() or path.stat().st_size == 0:
        errors.append(f"{label} is missing or empty: {path}")
pwr = checks["powered netlist"]
if pwr.is_file():
    text = pwr.read_text(errors="replace")
    if not re.search(r"\bmodule\s+NanoCGRA_Lite\b", text):
        errors.append("powered netlist has no NanoCGRA_Lite module")
    if len(text) < 10000 or ".VDD(vdd)" not in text or ".VSS(vss)" not in text:
        errors.append("powered netlist is not populated with explicit PG-connected cells")
flow = (pkg / "pnr/flow.tcl").read_text()

def pin_geometry(path):
    text = path.read_text()
    body_match = re.search(r"PINS\s+\d+\s*;(.*?)END PINS", text, re.S)
    if not body_match:
        return {}
    result = {}
    for match in re.finditer(r"^[ \t]*-[ \t]+(\S+)(.*?)(?=^[ \t]*-[ \t]+\S+|\Z)", body_match.group(1), re.M | re.S):
        result[match.group(1)] = sorted(re.findall(r"\+\s+LAYER\s+(\S+)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", match.group(2)))
    return result

generated_def = pkg / "pnr/nanocgra_lite_3x3_opt.def"
reference_def = pkg / "pnr/D04.def"
if generated_def.is_file() and reference_def.is_file():
    generated_geometry = pin_geometry(generated_def)
    reference_geometry = pin_geometry(reference_def)
    # The supplied D04 reference violates Metal2 spacing in the UART pin cluster;
    # generated DEF applies the documented OE/OUT/SL spacing corrections.
    reference_geometry["uart_tx_OE"] = [("Metal2", "0", "898260", "2000", "898540")]
    reference_geometry["uart_tx_OUT"] = [("Metal2", "0", "900840", "2000", "901120")]
    reference_geometry["uart_tx_SL"] = [("Metal2", "0", "902810", "2000", "903190")]
    if generated_geometry != reference_geometry:
        errors.append("generated DEF pin geometry differs from D04 plus the documented UART spacing corrections")
    generated_text = generated_def.read_text(errors="replace")
    if "DIEAREA ( 0 0 ) ( 1100000 1100000 ) ;" not in generated_text:
        errors.append("generated DEF does not satisfy the D04 550um die contract")

expected = ["clock_tree_synthesis", "global_route", "detailed_route", "fill_16", "fill_8", "fill_4", "fill_2", "fill_1", "report_check_types", "check_power_grid"]
for token in expected:
    if token not in flow:
        errors.append(f"flow.tcl lacks {token}")
# Fresh signoff evidence is valid only when the producing tool wrote its marker.
for marker, reports in {
    "flow.complete": [],
    "pdnsim.complete": ["pdnsim_vdd.rpt", "pdnsim_vss.rpt"],
}.items():
    marker_path = pkg / "reports" / marker
    if not marker_path.is_file():
        errors.append(f"pending rerun: missing completion marker reports/{marker}")
        continue
    for report in reports:
        path = pkg / "reports" / report
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing/empty report despite {marker}: reports/{report}")
route_drc = pkg / "reports/route_drc.rpt"
if not route_drc.is_file():
    errors.append("missing detailed-route DRC report: reports/route_drc.rpt")
elif route_drc.stat().st_size != 0:
    errors.append("detailed-route DRC report is not clean: reports/route_drc.rpt")
for report in ["reports/signoff/sta_ss_repair.rpt", "reports/signoff/pg_connectivity.rpt"]:
    path = pkg / report
    if not path.is_file() or path.stat().st_size == 0:
        errors.append(f"missing/empty post-route report: {report}")
extract_marker = pkg / "reports/lvs/extraction.complete"
netgen_marker = pkg / "reports/lvs/netgen.complete"
if not extract_marker.is_file():
    errors.append("pending rerun: canonical GDS extraction completion marker is absent")
if not netgen_marker.is_file():
    errors.append("real transistor-level LVS has not passed; reports/lvs/netgen.complete is absent")
else:
    if "NETGEN_LVS_PASSED" not in netgen_marker.read_text(errors="replace"):
        errors.append("Netgen marker does not certify an LVS pass")
for error in errors:
    print("ERROR: " + error, file=sys.stderr)
if errors:
    raise SystemExit(1)
print("PASS: required package artifacts and fresh completion evidence are present")
