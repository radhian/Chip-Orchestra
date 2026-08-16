from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reporting import (
    ARCHITECTURE_PATH,
    FINAL_REPORT_PATH,
    PDF_PATH,
    RUNBOOK_PATH,
    collect_evidence,
    generate_pdf,
    generate_reports,
)


def _seed_workspace(tmp_path: Path) -> None:
    for sub in ("rtl", "tb", "reports", "waves", "gds", "padring"):
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
    padring_report = {
        "stage": "PADRING",
        "config": "gf180-v1",
        "summary": "padring ok",
        "pad_summary": {"analog": 58, "clk": 1, "rst_n": 1, "uart_rx": 1, "uart_tx": 1, "dvdd": 3, "dvss": 4, "corners": 4, "total_io": 69},
        "metrics": {"pdk": "gf180mcuD", "die_width_um": 2935.0, "die_height_um": 2935.0, "pads_total_io": 69},
        "artifacts": [{"path": "padring/alu_chip_preview.png", "kind": "layout_preview"}],
    }
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lF3N7wAAAABJRU5ErkJggg==")
    (tmp_path / "padring/alu_chip_preview.png").write_bytes(png)
    (tmp_path / "reports/sim_report.json").write_text(json.dumps(sim_report))
    (tmp_path / "reports/drc_lvs_report.json").write_text(json.dumps(drc_report))
    (tmp_path / "reports/padring_report.json").write_text(json.dumps(padring_report))


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


def test_generate_pdf_includes_padring_section(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    ctx = collect_evidence("task-1", tmp_path, {"task_name": "alu", "design_brief": "An ALU"})
    pdf = generate_pdf(tmp_path, ctx)
    if pdf is None:
        return

    out = tmp_path / PDF_PATH
    assert out.is_file()
    assert out.stat().st_size > 0
    assert "PADRING" in ctx.stage_reports
    assert ctx.metrics["pads_total_io"] == 69


# --------------------------------------------------------------------------- #
# HW/SW co-verification chapter + discovered references
# --------------------------------------------------------------------------- #
HW_SW_REPORT = {
    "stage": "HW_SW_VERIFY",
    "completed": True,
    "summary": "The chip processed road.png and returned what the model computes.",
    "input": {"path": "hwsw/input/road.png", "name": "road.png",
              "bytes_in": 1024, "bytes_out": 900},
    "interface": {
        "kind": "serial",
        "description": "Interface is BIT-SERIAL (UART-style) on data_i/data_o.",
        "clock": "clk", "reset": "rst_async_n",
        "data_in": ["data_i"], "data_out": ["data_o"],
        "constants": {"CLK_FREQ": 50000000, "BAUD_RATE": 115200, "BAUD_DIV": 434, "DATA_W": 8},
        "driver": "sw/hwsw/host_driver.py",
        "testbench": "tb/hwsw/alu_hwsw_tb.v",
        "testbench_origin": "derived from tb/alu_tb.v",
    },
    "metrics": {"match": True, "checked": True, "bytes_sent": 1024, "bytes_received": 900,
                "bytes_expected": 900, "mismatches": 0, "max_abs_diff": 0,
                "golden_source": "golden/model/top.py::sobel_stream"},
    "previews": ["hwsw/input_preview.png", "hwsw/chip_output.png"],
    "errors": [],
}


def test_hw_sw_metrics_stay_out_of_the_implementation_metrics(tmp_path: Path) -> None:
    """Byte counts describe a transfer, not the silicon. Merging them into the
    shared metrics dict would put "mismatches" next to die area."""
    _seed_workspace(tmp_path)
    (tmp_path / "reports/hw_sw_verify_report.json").write_text(json.dumps(HW_SW_REPORT))
    (tmp_path / "reports/pnr_report.json").write_text(
        json.dumps({"stage": "PNR", "metrics": {"die_area_um2": 246939}}))

    ctx = collect_evidence("task-1", tmp_path, {"task_name": "alu"})

    assert ctx.hw_sw["metrics"]["bytes_received"] == 900
    assert ctx.metrics.get("die_area_um2") == 246939
    assert "bytes_received" not in ctx.metrics and "mismatches" not in ctx.metrics


def test_latex_gains_a_hardware_software_chapter(tmp_path: Path) -> None:
    from reporting.latex_report import generate_latex

    _seed_workspace(tmp_path)
    (tmp_path / "reports/hw_sw_verify_report.json").write_text(json.dumps(HW_SW_REPORT))
    ctx = collect_evidence("task-1", tmp_path, {"task_name": "alu"})
    tex = generate_latex(ctx, ["hwsw/input_preview.png", "hwsw/chip_output.png"])

    assert "\\section{Hardware/Software Co-Verification}" in tex
    assert "\\label{sec:hwsw}" in tex
    assert "host\\_\\allowbreak{}driver" in tex          # the software half is named
    assert "hwsw/chip_output.png" in tex                 # and its result is shown
    assert "sobel\\_\\allowbreak{}stream" in tex         # the reference it was checked against
    assert "Verdict & match" in tex
    # The introduction must point at the new section rather than skip over it.
    assert "Section~\\ref{sec:hwsw}" in tex


def test_no_hardware_software_chapter_when_the_stage_did_not_run(tmp_path: Path) -> None:
    """A report must never describe a verification that did not happen."""
    from reporting.latex_report import generate_latex

    _seed_workspace(tmp_path)
    ctx = collect_evidence("task-1", tmp_path, {"task_name": "alu"})
    assert "Hardware/Software Co-Verification" not in generate_latex(ctx, [])

    # Nor when the stage ran but failed to complete.
    (tmp_path / "reports/hw_sw_verify_report.json").write_text(
        json.dumps({**HW_SW_REPORT, "completed": False, "errors": ["co-simulation timed out"]}))
    ctx = collect_evidence("task-1", tmp_path, {"task_name": "alu"})
    assert "Hardware/Software Co-Verification" not in generate_latex(ctx, [])


def test_markdown_report_carries_the_same_chapter(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    (tmp_path / "reports/hw_sw_verify_report.json").write_text(json.dumps(HW_SW_REPORT))
    ctx = collect_evidence("task-1", tmp_path, {"task_name": "alu"})

    body = generate_reports(ctx)[FINAL_REPORT_PATH]
    assert "## Hardware/Software Co-Verification" in body
    assert "sw/hwsw/host_driver.py" in body
    assert "road.png" in body


def test_discovered_references_are_cited_and_listed(tmp_path: Path) -> None:
    from reporting.latex_report import generate_latex

    _seed_workspace(tmp_path)
    (tmp_path / "exports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "exports/related_work.json").write_text(json.dumps({
        "summary": "Sobel accelerators are well studied.",
        "references": [
            {"authors": "R. Gonzalez and R. Woods", "title": "Digital Image Processing",
             "venue": "Pearson, 2018", "url": "https://example.org/dip",
             "relation": "the standard reference for the operator this chip implements"},
            # No title -> not citable, must be dropped rather than printed empty.
            {"authors": "Anon", "relation": "unusable"},
        ],
    }))
    ctx = collect_evidence("task-1", tmp_path, {"task_name": "alu"})
    tex = generate_latex(ctx, [])

    assert "\\section{Related Work}" in tex
    assert "\\cite{r1}" in tex
    assert "\\bibitem{r1}" in tex
    assert "\\url{https://example.org/dip}" in tex
    assert "\\bibitem{r2}" not in tex, "an entry with no title is not a reference"
    # The toolchain citations must survive alongside the discovered ones.
    assert "\\bibitem{b1}" in tex and "\\bibitem{b4}" in tex
