from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reporting import (
    ARCHITECTURE_PATH,
    FINAL_REPORT_PATH,
    RUNBOOK_PATH,
    collect_evidence,
    generate_reports,
)


def _seed_workspace(tmp_path: Path) -> None:
    for sub in ("rtl", "tb", "reports", "waves", "gds"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "rtl/alu.sv").write_text("module alu; endmodule\n")
    (tmp_path / "tb/alu_tb.sv").write_text("module alu_tb; endmodule\n")
    (tmp_path / "waves/design.vcd").write_text("$date $end\n")
    (tmp_path / "gds/alu.gds").write_text("GDS")
    (tmp_path / "reports/rtl_architecture.md").write_text("# arch\n")
    sim_report = {"stage": "SIM", "compiled": True, "waveform": True, "summary": "ok"}
    drc_report = {
        "stage": "DRC_LVS",
        "metrics": {"wns_ns": 0.2, "area_um2": 1200},
        "signoff": {"failed": []},
        "tapeout_ready": True,
    }
    (tmp_path / "reports/sim_report.json").write_text(json.dumps(sim_report))
    (tmp_path / "reports/drc_lvs_report.json").write_text(json.dumps(drc_report))


def test_collect_evidence_scans_workspace_and_reports(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    ctx = collect_evidence("task-1", tmp_path, {"task_name": "alu", "design_brief": "An ALU"})

    assert ctx.top_module == "alu"
    assert "rtl/alu.sv" in ctx.rtl_files
    assert "waves/design.vcd" in ctx.wave_files
    assert ctx.tapeout_ready is True
    assert ctx.metrics["wns_ns"] == 0.2
    assert ctx.simulation["waveform"] is True


def test_generate_reports_produces_three_markdown_files(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    ctx = collect_evidence("task-1", tmp_path, {"task_name": "alu", "design_brief": "An ALU"})
    reports = generate_reports(ctx)

    assert set(reports.keys()) == {FINAL_REPORT_PATH, ARCHITECTURE_PATH, RUNBOOK_PATH}
    assert "Final Design Report" in reports[FINAL_REPORT_PATH]
    assert "tapeout ready" in reports[FINAL_REPORT_PATH]
    assert "alu" in reports[ARCHITECTURE_PATH]
    assert "iverilog" in reports[RUNBOOK_PATH]
