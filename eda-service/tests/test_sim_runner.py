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


def test_a_spec_top_that_names_no_module_still_picks_the_chip_testbench(
    tmp_path: Path,
) -> None:
    """SPEC_INGEST derives spec.json's top_module from the TASK NAME, so it can
    name no module at all once GOLDEN_GEN picks the real top. When that happened
    both selectors missed and the "largest tb" fallback simulated a UNIT tb as
    if it were the chip: green SIM, no chip output, no waveform."""
    ws = ensure_workspace("task-top-drift", tmp_path)
    (ws / "rtl" / "pe.v").write_text("module pe(input clk); endmodule\n")
    (ws / "rtl" / "top.v").write_text(
        "module sobel_top(input clk);\n  pe u_pe(.clk(clk));\nendmodule\n")
    # The unit tb is deliberately the LARGEST file — the old fallback chose it.
    (ws / "tb" / "pe_tb.v").write_text(
        "module pe_tb;\n  pe dut();\n" + "  // padding\n" * 40 + "endmodule\n")
    (ws / "tb" / "sobel_top_tb.v").write_text(
        "module sobel_top_tb;\n  sobel_top dut();\nendmodule\n")
    runner = FakeCommandRunner(write_vcd=True)

    report = run_simulation(
        ws,
        [ws / "rtl" / "pe.v", ws / "rtl" / "top.v",
         ws / "tb" / "pe_tb.v", ws / "tb" / "sobel_top_tb.v"],
        "nano_cgra_3x3_for_sobel_accelerator",   # the task-name slug
        {},
        runner,
    )

    compile_args = " ".join(next(c for c in runner.calls if Path(c[0]).name == "iverilog"))
    assert "sobel_top_tb.v" in compile_args
    assert "pe_tb.v" not in compile_args
    assert report.top == "sobel_top"
    assert any("not a module in rtl/" in w for w in report.warnings)


def test_a_top_the_rtl_declares_is_left_alone(tmp_path: Path) -> None:
    ws = _seed_workspace(tmp_path)
    runner = FakeCommandRunner(write_vcd=True)

    report = run_simulation(
        ws, [ws / "rtl" / "uart_top.sv", ws / "tb" / "uart_top_tb.sv"],
        "uart_top", {}, runner)

    assert report.top == "uart_top"
    assert not any("not a module in rtl/" in w for w in report.warnings)


def _grid(side: int, fill: int = 7) -> list:
    return [fill] * (side * side)


def test_border_only_mismatches_are_named_as_a_padding_bug(tmp_path: Path) -> None:
    """12 truncated `index N: golden=X chip=Y` lines told the repair agent
    nothing about the CLASS of bug; it burned ten rounds guessing while every
    interior pixel already matched."""
    from toolchain.sim_runner import _mismatch_shape

    (tmp_path / "context").mkdir(parents=True)
    (tmp_path / "context" / "input_size.txt").write_text("32")
    golden = _grid(32)
    chip = list(golden)
    for r in range(32):                      # corrupt only columns 0 and 31
        chip[r * 32] = 1
        chip[r * 32 + 31] = 1

    shape = _mismatch_shape(golden, chip, tmp_path)
    assert "64 of 1024" in shape
    assert "cols 0,31" in shape
    assert "BORDER" in shape
    assert "NOT a datapath bug" in shape


def test_a_total_mismatch_is_named_as_a_datapath_bug(tmp_path: Path) -> None:
    from toolchain.sim_runner import _mismatch_shape

    (tmp_path / "context").mkdir(parents=True)
    (tmp_path / "context" / "input_size.txt").write_text("32")
    golden = _grid(32, 7)
    chip = _grid(32, 9)

    shape = _mismatch_shape(golden, chip, tmp_path)
    assert "1024 of 1024" in shape
    assert "EVERY value differs" in shape


def test_a_matching_output_has_no_shape_report(tmp_path: Path) -> None:
    from toolchain.sim_runner import _mismatch_shape

    g = _grid(8)
    assert _mismatch_shape(g, list(g), tmp_path) == ""


def test_zero_mismatches_is_not_a_failure() -> None:
    """A testbench printing "0 mismatches" was marked FAILED by a bare
    `mismatch` match, while the golden compare on the next line said the output
    matched value-for-value."""
    import re

    pat = (r"FAILED|\$fatal|ERROR:|assert(ion)?\s+fail"
           r"|(?<![0-9])[1-9][0-9]*\s+mismatch"
           r"|\bmismatch(?!es\b)(?!\s*[:=]?\s*0\b)")

    clean = "received 1024 of 1024 bytes, 0 mismatches\ntb: ALL TESTS PASSED"
    assert not re.search(pat, clean, re.I)

    for bad in ("received 1024 of 1024 bytes, 34 mismatches",
                "tb: FAILED", "ERROR: bad value", "assertion failed"):
        assert re.search(pat, bad, re.I), bad


# --------------------------------------------------------------------------- #
# "403 of 900 values differ" sends a repair agent hunting the whole datapath.
# Deriving the LAW that relates chip to golden turns the same data into a
# one-line diagnosis. The real v4 SIM failure was chip == (golden>>1)|0x80 on
# every odd byte — a byte-boundary off-by-one in the serialiser.
# --------------------------------------------------------------------------- #
def _law(golden, chip):
    from toolchain.sim_runner import _mismatch_law
    return _mismatch_law(golden, chip)


def test_serial_off_by_one_bit_is_named() -> None:
    golden = [(i * 7 + 3) & 0xFF for i in range(200)]
    chip = [((v >> 1) | 0x80) if i % 2 else v for i, v in enumerate(golden)]
    law = _law(golden, chip)
    assert "golden >> 1" in law and "0x80" in law
    assert "every ODD index" in law
    assert "ALL 100 mismatching" in law


def test_pipeline_lag_is_named_as_alignment_not_datapath() -> None:
    golden = [(i * 13 + 5) & 0xFF for i in range(120)]
    chip = [0] + golden[:-1]
    law = _law(golden, chip)
    assert "golden[i-1]" in law and "LAGS" in law
    assert "NOT a datapath bug" in law


def test_a_stuck_high_bit_is_named_as_stuck_not_offset() -> None:
    golden = [(i * 3) & 0x3F for i in range(64)]
    chip = [v | 0x40 for v in golden]
    law = _law(golden, chip)
    assert "STUCK HIGH" in law and "0x40" in law


def test_a_matching_run_yields_no_law() -> None:
    vals = [(i * 5) & 0xFF for i in range(50)]
    assert _law(vals, vals) == ""


def test_unexplainable_mismatches_do_not_invent_a_law() -> None:
    import random
    random.seed(7)
    golden = [random.randint(0, 255) for _ in range(200)]
    chip = list(golden)
    for i in (3, 17, 42, 91, 150):          # scattered, unrelated corruption
        chip[i] = (golden[i] * 31 + 17) & 0xFF
    law = _law(golden, chip)
    assert "SYSTEMATIC" not in law


# --------------------------------------------------------------------------- #
# A 5.7 GB design.vcd (real baud timing + $dumpvars(0,tb) + a 100M-cycle
# watchdog) was read whole into a Python string and OOM-killed eda-service
# mid-stage, orphaning SIM. The waveform is a preview; results come from stdout
# and .mem files, so the dump must never be parsed unbounded.
# --------------------------------------------------------------------------- #
def test_a_normal_vcd_is_not_flagged() -> None:
    from toolchain.sim_runner import _vcd_too_big

    assert _vcd_too_big(8 * 1024 * 1024) == ""


def test_an_oversized_vcd_is_flagged_with_actionable_advice() -> None:
    from toolchain.sim_runner import _vcd_too_big

    msg = _vcd_too_big(6 * 1024 * 1024 * 1024)
    assert msg
    assert "waveform preview SKIPPED" in msg
    assert "UNAFFECTED" in msg              # results still trustworthy
    assert "$dumpvars(1, tb)" in msg        # narrow the dump
    assert "BAUD_DIV" in msg                # don't simulate real baud timing


def test_the_vcd_cap_is_configurable(monkeypatch) -> None:
    from toolchain import sim_runner

    monkeypatch.setenv("SIM_MAX_VCD_MB", "1")
    assert sim_runner._vcd_too_big(2 * 1024 * 1024)
    assert sim_runner._vcd_too_big(512 * 1024) == ""


def test_a_bad_cap_value_falls_back_to_the_default(monkeypatch) -> None:
    from toolchain import sim_runner

    monkeypatch.setenv("SIM_MAX_VCD_MB", "not-a-number")
    assert sim_runner._max_vcd_bytes() == 256 * 1024 * 1024


# --------------------------------------------------------------------------- #
# GL_SIM handed iverilog EVERY library under libs.ref/ — two standard-cell
# families at once (mcu7t5v0 + mcu9t5v0) whose primitives.v declare the same
# modules — and every testbench in tb/, including unit benches that
# `include "params.vh"`. Elaboration died with "Unknown module type" for cells
# that were in fact defined.
# --------------------------------------------------------------------------- #
def test_only_the_cell_library_the_netlist_uses_is_passed(tmp_path, monkeypatch) -> None:
    from toolchain import gl_sim

    pdk = tmp_path / "pdk" / "gf180mcuD" / "libs.ref"
    for lib in ("gf180mcu_fd_sc_mcu7t5v0", "gf180mcu_fd_sc_mcu9t5v0", "gf180mcu_fd_ip_sram"):
        d = pdk / lib / "verilog"
        d.mkdir(parents=True)
        (d / f"{lib}.v").write_text("// models\n")
        (d / "primitives.v").write_text("// primitives\n")
    monkeypatch.setenv("PDK_ROOT", str(tmp_path / "pdk"))
    monkeypatch.setenv("PDK", "gf180mcuD")

    nl = tmp_path / "design.nl.v"
    nl.write_text("module top(); gf180mcu_fd_sc_mcu7t5v0__antenna a(); endmodule\n")

    got = gl_sim._find_cell_models(str(nl))
    assert any("mcu7t5v0" in g for g in got), got
    assert not any("mcu9t5v0" in g for g in got), got
    # non-standard-cell models (SRAM/IO macros) must still come along
    assert any("ip_sram" in g for g in got), got


def test_an_unreadable_netlist_falls_back_to_every_library(tmp_path, monkeypatch) -> None:
    from toolchain import gl_sim

    d = tmp_path / "pdk" / "gf180mcuD" / "libs.ref" / "gf180mcu_fd_sc_mcu7t5v0" / "verilog"
    d.mkdir(parents=True)
    (d / "cells.v").write_text("// models\n")
    monkeypatch.setenv("PDK_ROOT", str(tmp_path / "pdk"))
    monkeypatch.setenv("PDK", "gf180mcuD")

    assert gl_sim._find_cell_models("") == gl_sim._find_cell_models("/nonexistent.v")
