"""Run the existing NanoCGRA RTL through repository EDA runners."""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eda-service"))
from toolchain import run_simulation, run_lint, run_harden, run_padring
from toolchain import padring_runner
padring_runner._render_gds_preview = lambda *args, **kwargs: False

workspace = ROOT / "paper" / "nanocgra_e2e_20261011"
(workspace / "reports").mkdir(exist_ok=True)
top = "NanoCGRA_Lite"
manifest = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "workspace": str(workspace), "input": "output/nanocgra_lite_3x3_opt/rtl",
            "mode": "Direct repository EDA runners on existing RTL, without AI regeneration",
            "stages": {}}

def save(name, report):
    data = report.as_dict()
    (workspace / "reports" / f"{name.lower()}_report.json").write_text(json.dumps(data, indent=2))
    manifest["stages"][name] = data
    (workspace / "reports" / "execution_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(name, report.summary, "errors=", report.errors, flush=True)
    return data

rtl = sorted((workspace / "rtl").glob("*.v"))
tb = sorted((workspace / "tb").glob("*.v"))
sim = run_simulation(workspace, rtl + tb, top)
save("SIM", sim)
lint = run_lint(workspace, rtl, top)
save("LINT", lint)
if sim.errors or lint.errors:
    raise SystemExit("Functional prechecks failed. See stage reports.")
hard = run_harden(workspace, top, "clk", 100.0,
                  {"voltage": "5v0", "core_util": 55}, stage="PNR")
save("HARDEN", hard)
if not hard.gds:
    raise SystemExit("Fresh hardening failed. No new GDS was produced.")
pad = run_padring(workspace, top, {"padring": "gf180-v1"})
save("PADRING", pad)
manifest["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
(workspace / "reports" / "execution_manifest.json").write_text(json.dumps(manifest, indent=2))
print("DONE", pad.gds, flush=True)
