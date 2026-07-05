from __future__ import annotations

import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runner import CommandResult
from toolchain.sim_runner import run_simulation
from workspace import ensure_workspace


VCD_TEXT = """$timescale 1ns $end
$var wire 1 ! clk $end
$var wire 8 " data $end
$enddefinitions $end
#0
0!
b00000000 "
#5
1!
b00000001 "
"""


class FakeCommandRunner:
    """Fake runner that records calls, emits canned logs and writes fake outputs."""

    def __init__(self, *, write_vcd: bool = True):
        self.calls: List[list] = []
        self.write_vcd = write_vcd

    def run(self, args, *, cwd=None, timeout=None, env=None) -> CommandResult:
        self.calls.append([str(a) for a in args])
        prog = Path(str(args[0])).name
        if prog == "iverilog":
            # simulate producing the vvp image
            out_idx = [str(a) for a in args].index("-o") + 1
            Path(str(args[out_idx])).write_text("VVP_IMAGE")
            return CommandResult(args=[str(a) for a in args], returncode=0, stderr="", stdout="")
        if prog == "vvp":
            if self.write_vcd and cwd is not None:
                (Path(cwd) / "design.vcd").write_text(VCD_TEXT)
            return CommandResult(args=[str(a) for a in args], returncode=0, stdout="TEST PASSED\n")
        return CommandResult(args=[str(a) for a in args], returncode=0)


def _seed_workspace(tmp_path: Path) -> Path:
    ws = ensure_workspace("task-sim", tmp_path)
    (ws / "rtl" / "uart_top.sv").write_text("module uart_top(input clk); endmodule\n")
    (ws / "tb" / "uart_top_tb.sv").write_text("module uart_top_tb; endmodule\n")
    return ws


def test_run_simulation_compiles_runs_and_detects_waveform(tmp_path: Path) -> None:
    ws = _seed_workspace(tmp_path)
    runner = FakeCommandRunner(write_vcd=True)

    report = run_simulation(ws, [ws / "rtl" / "uart_top.sv", ws / "tb" / "uart_top_tb.sv"], "uart_top_tb", {}, runner)

    assert report.stage == "SIM"
    assert report.compiled is True
    assert report.waveform is True
    assert report.waveform_summary.get("signals")
    # sim log + vcd registered as artifacts
    paths = {a["path"] for a in report.artifacts}
    assert "logs/sim.log" in paths
    assert "waves/design.vcd" in paths
    assert (ws / "logs" / "sim.log").is_file()
    # both iverilog and vvp were invoked
    progs = {Path(c[0]).name for c in runner.calls}
    assert {"iverilog", "vvp"} <= progs


def test_run_simulation_reports_missing_iverilog(tmp_path: Path) -> None:
    ws = _seed_workspace(tmp_path)

    class MissingRunner:
        def run(self, args, *, cwd=None, timeout=None, env=None):
            return CommandResult(args=[str(a) for a in args], returncode=127, not_found=True,
                                 stderr="iverilog not found")

    report = run_simulation(ws, [ws / "rtl" / "uart_top.sv"], "uart_top", {}, MissingRunner())

    assert report.compiled is False
    assert "iverilog not available" in report.errors


def test_run_simulation_without_waveform_warns(tmp_path: Path) -> None:
    ws = _seed_workspace(tmp_path)
    runner = FakeCommandRunner(write_vcd=False)

    report = run_simulation(ws, [ws / "rtl" / "uart_top.sv", ws / "tb" / "uart_top_tb.sv"], "uart_top_tb", {}, runner)

    assert report.compiled is True
    assert report.waveform is False
    assert any("no waveform" in w for w in report.warnings)


def test_run_simulation_no_sources(tmp_path: Path) -> None:
    ws = ensure_workspace("task-empty", tmp_path)
    report = run_simulation(ws, [], "", {}, FakeCommandRunner())
    assert report.compiled is False
    assert report.errors
