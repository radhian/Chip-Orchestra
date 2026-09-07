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
for key in ("LAYOUT_FILE", "LVS_LAYOUT_SPICE"):
    value = data.get(key, "")
    if not value.startswith("$UPRJ_ROOT/"):
        errors.append(f"{key} must be rooted at $UPRJ_ROOT: {value}")
if "_filled.gds" in data.get("LAYOUT_FILE", ""):
    errors.append("LAYOUT_FILE names a filled GDS")
verilog = data.get("LVS_VERILOG_FILES", [])
if len(verilog) != 1 or not verilog[0].endswith("nanocgra_lite_3x3_opt.pnr.pwr.v"):
    errors.append("LVS_VERILOG_FILES must contain the powered post-route netlist")
for unsupported in ("LVS_SPICE_FILES", "LVS_EXTRACT_SCRIPT", "LVS_RUN_SCRIPT", "LVS_FINAL_LOG"):
    if unsupported in data:
        errors.append(f"{unsupported} is unsupported or redundant in the integration LVS config")
root = os.environ.get("UPRJ_ROOT", "")
for key, values in (
    ("LVS_VERILOG_FILES", verilog),
    ("LAYOUT_FILE", [data.get("LAYOUT_FILE", "")]),
    ("LVS_LAYOUT_SPICE", [data.get("LVS_LAYOUT_SPICE", "")]),
):
    for value in values:
        expanded = value.replace("$UPRJ_ROOT", root)
        if not expanded or not Path(expanded).is_file() or Path(expanded).stat().st_size == 0:
            errors.append(f"{key} missing/empty after env expansion: {expanded}")
for error in errors:
    print("ERROR: " + error, file=sys.stderr)
if errors:
    raise SystemExit(1)
print("PASS: LVS config uses the supported base config, canonical layout, and powered Verilog inputs")
