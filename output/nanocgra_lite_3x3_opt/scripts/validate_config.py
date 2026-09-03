#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: validate_config.py lvs_config.json")
config_path = Path(sys.argv[1])
data = json.loads(config_path.read_text())
errors = []
for key in ("LAYOUT_FILE", "LVS_LAYOUT_SPICE", "LVS_EXTRACT_SCRIPT", "LVS_RUN_SCRIPT", "LVS_FINAL_LOG"):
    value = data.get(key, "")
    if not value.startswith("$UPRJ_ROOT/"):
        errors.append(f"{key} must be rooted at $UPRJ_ROOT: {value}")
if "_filled.gds" in data.get("LAYOUT_FILE", ""):
    errors.append("LAYOUT_FILE names a filled GDS")
verilog = data.get("LVS_VERILOG_FILES", [])
if len(verilog) != 1 or not verilog[0].endswith("nanocgra_lite_3x3_opt.pnr.pwr.v"):
    errors.append("LVS_VERILOG_FILES must contain the powered post-route netlist")
spice = data.get("LVS_SPICE_FILES", [])
if len(spice) != 1 or not spice[0].startswith("$PDK_ROOT/") or not spice[0].endswith(".cdl"):
    errors.append("LVS_SPICE_FILES must contain the official PDK standard-cell CDL")
root = os.environ.get("UPRJ_ROOT", "")
pdk = os.environ.get("PDK_ROOT", "")
for key, values in (("LVS_VERILOG_FILES", verilog), ("LVS_SPICE_FILES", spice),
                    ("LAYOUT_FILE", [data.get("LAYOUT_FILE", "")]),
                    ("LVS_EXTRACT_SCRIPT", [data.get("LVS_EXTRACT_SCRIPT", "")]),
                    ("LVS_RUN_SCRIPT", [data.get("LVS_RUN_SCRIPT", "")])):
    for value in values:
        expanded = value.replace("$UPRJ_ROOT", root).replace("$PDK_ROOT", pdk)
        if not expanded or not Path(expanded).is_file() or Path(expanded).stat().st_size == 0:
            errors.append(f"{key} missing/empty after env expansion: {expanded}")
for error in errors:
    print("ERROR: " + error, file=sys.stderr)
if errors:
    raise SystemExit(1)
print("PASS: LVS config uses environment-rooted canonical layout, powered Verilog, and official CDL")
