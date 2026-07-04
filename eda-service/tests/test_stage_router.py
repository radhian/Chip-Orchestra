from __future__ import annotations

import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobs import run_stage
from runner import CommandResult
from toolchain.reports import DrcLvsReport, LintReport, PnrReport, SignoffReport, SimReport, SynthReport
from workspace import ensure_workspace


class RecordingRunner:
    """Runner that records invocations and fabricates minimal successful outputs."""

    def __init__(self):
        self.programs: List[str] = []

    def run(self, args, *, cwd=None, timeout=None, env=None) -> CommandResult:
        prog = Path(str(args[0])).name
        self.programs.append(prog)
        arglist = [str(a) for a in args]
        if prog == "iverilog" and "-o" in arglist:
            out = arglist[arglist.index("-o") + 1]
            Path(out).write_text("VVP")
            return CommandResult(args=arglist, returncode=0)
        if prog == "vvp" and cwd is not None:
            (Path(cwd) / "design.vcd").write_text(
                "$var wire 1 ! clk $end\n$enddefinitions $end\n#0\n0!\n#5\n1!\n"
            )
            return CommandResult(args=arglist, returncode=0, stdout="done")
        if prog == "librelane" and cwd is not None:
            final = Path(cwd) / "runs" / "R" / "final" / "gds"
            final.mkdir(parents=True, exist_ok=True)
            (final / "top.gds").write_text("GDS")
            (Path(cwd) / "runs" / "R" / "metrics.json").write_text(
                '{"design__die__area": 100, "magic__drc_error__count": 0, "timing__setup__ws": 0.1}'
            )
            return CommandResult(args=arglist, returncode=0, stdout="flow complete")
        return CommandResult(args=arglist, returncode=0)


def _ws(tmp_path: Path, name: str) -> Path:
    ws = ensure_workspace(name, tmp_path)
    (ws / "rtl" / "top.v").write_text(
        "module top(input clk, output reg q); always @(posedge clk) q<=1'b1; endmodule\n"
    )
    (ws / "tb" / "top_tb.v").write_text("module top_tb; endmodule\n")
    return ws


def test_sim_stage_dispatches_to_sim_runner(tmp_path: Path) -> None:
    ws = _ws(tmp_path, "t-sim")
    runner = RecordingRunner()
    report = run_stage(stage="SIM", task_id="t-sim", workspace=ws, opts={"top_module": "top_tb"}, runner=runner)
    assert isinstance(report, SimReport)
    assert report.compiled is True
    assert "iverilog" in runner.programs


def test_lint_stage_dispatches_to_lint_runner(tmp_path: Path) -> None:
    ws = _ws(tmp_path, "t-lint")
    runner = RecordingRunner()
    report = run_stage(stage="LINT", task_id="t-lint", workspace=ws, opts={}, runner=runner)
    assert isinstance(report, LintReport)
    assert report.clean is True
    assert "iverilog" in runner.programs


def test_synth_pnr_drc_dispatch_to_harden_runner(tmp_path: Path) -> None:
    expected = {"SYNTH": SynthReport, "PNR": PnrReport, "DRC_LVS": DrcLvsReport}
    for stage, cls in expected.items():
        ws = _ws(tmp_path, f"t-{stage.lower()}")
        runner = RecordingRunner()
        report = run_stage(stage=stage, task_id="t", workspace=ws, opts={"top_module": "top"}, runner=runner)
        assert isinstance(report, cls)
        assert report.stage == stage
        assert "librelane" in runner.programs
        assert report.tapeout_ready is True


def test_signoff_stage_produces_signoff_report(tmp_path: Path) -> None:
    ws = _ws(tmp_path, "t-signoff")
    report = run_stage(stage="SIGNOFF", task_id="t-signoff", workspace=ws, opts={}, runner=RecordingRunner())
    assert isinstance(report, SignoffReport)
    assert report.tapeout_ready is True


def test_unknown_stage_falls_back_to_mock(tmp_path: Path) -> None:
    ws = _ws(tmp_path, "t-unknown")
    report = run_stage(stage="CUSTOM", task_id="t", workspace=ws, opts={}, runner=RecordingRunner())
    assert report.stage == "CUSTOM"
    assert "Mock" in report.summary
    assert report.metrics
