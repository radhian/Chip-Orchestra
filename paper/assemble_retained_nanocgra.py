"""Assemble the retained NanoCGRA core, independently of fresh hardening."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eda-service"))
from toolchain import run_padring
from toolchain import padring_runner
# KLayout captures the actual GDS directly. Skip the expensive flattened
# Matplotlib preview without changing assembly or its returned metrics.
padring_runner._render_gds_preview = lambda *args, **kwargs: False
ws = ROOT / "paper" / "nanocgra_padframe_20261011"
(ws / "reports").mkdir(exist_ok=True)
report = run_padring(ws, "NanoCGRA_Lite", {"padring": "gf180-v1"})
data = report.as_dict()
data["provenance"] = {
    "core_source": "output/nanocgra_lite_3x3_opt/gds/nanocgra_lite_3x3_opt.gds",
    "core_implementation": "retained existing core, not a fresh hardening result",
    "assembly": "new run of repository padframe backend",
    "full_chip_signoff": False,
}
(ws / "reports" / "padring_report.json").write_text(json.dumps(data, indent=2))
print(json.dumps(data["metrics"], indent=2))
