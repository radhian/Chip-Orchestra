from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runner import CommandResult
from toolchain.harden_runner import run_harden
from workspace import ensure_workspace


FAKE_METRICS = {
    "design__die__area": 12345,
    "design__core__area": 10000,
    "design__instance__utilization": 42.1,
    "timing__setup__ws": 0.08,
    "power__total": 3.7,
    "magic__drc_error__count": 0,
    "route__drc_errors": 0,
    "lvs__total__errors": 0,
}


class FakeHardenRunner:
    """Fake runner that writes a fake GDS + metrics.json under the run dir."""

    def __init__(self, *, produce_gds: bool = True, clean: bool = True):
        self.calls: List[list] = []
        self.produce_gds = produce_gds
        self.clean = clean

    def run(self, args, *, cwd=None, timeout=None, env=None) -> CommandResult:
        self.calls.append([str(a) for a in args])
        if cwd is not None and self.produce_gds:
            final = Path(cwd) / "runs" / "RUN_1" / "final" / "gds"
            final.mkdir(parents=True, exist_ok=True)
            (final / "uart_top.gds").write_text("FAKE_GDS")
            render = Path(cwd) / "runs" / "RUN_1" / "final" / "render"
            render.mkdir(parents=True, exist_ok=True)
            (render / "layout.png").write_bytes(b"\x89PNG\r\n")
            metrics = dict(FAKE_METRICS)
            if not self.clean:
                metrics["magic__drc_error__count"] = 3
            (Path(cwd) / "runs" / "RUN_1" / "metrics.json").write_text(json.dumps(metrics))
        return CommandResult(args=[str(a) for a in args], returncode=0, stdout="LibreLane flow complete\n")


def _seed(tmp_path: Path) -> Path:
    ws = ensure_workspace("task-hard", tmp_path)
    (ws / "rtl" / "uart_top.v").write_text(
        "module uart_top(input clk, input rst, output reg q);\n"
        "  always @(posedge clk) q <= rst;\n"
        "endmodule\n"
    )
    return ws


def test_run_harden_produces_gds_metrics_and_signoff(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    runner = FakeHardenRunner(produce_gds=True, clean=True)

    report = run_harden(ws, top="uart_top", clock_port="clk", clock_period=20.0, runner=runner, stage="SYNTH")

    assert report.stage == "SYNTH"
    assert report.top == "uart_top"
    assert report.gds == "gds/uart_top.gds"
    assert report.png == "gds/uart_top.png"
    assert report.tapeout_ready is True
    assert report.signoff["clean"] is True
    assert report.metrics["die_area_um2"] == 12345
    assert report.metrics["power_mw"] == 3.7
    assert (ws / "gds" / "uart_top.gds").is_file()
    paths = {a["path"] for a in report.artifacts}
    assert {"gds/uart_top.gds", "gds/uart_top.png", "logs/librelane.log"} <= paths
    # config.json was synthesized
    cfg = json.loads((ws / "exports" / "harden" / "chip" / "config.json").read_text())
    assert cfg["DESIGN_NAME"] == "uart_top"
    assert cfg["CLOCK_PORT"] == "clk"


def test_run_harden_dirty_signoff_not_tapeout_ready(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    runner = FakeHardenRunner(produce_gds=True, clean=False)

    report = run_harden(ws, top="uart_top", runner=runner, stage="DRC_LVS")

    assert report.stage == "DRC_LVS"
    assert report.signoff["clean"] is False
    assert report.tapeout_ready is False
    assert "magic_drc" in report.signoff["failed"]


def test_run_harden_missing_librelane(tmp_path: Path) -> None:
    ws = _seed(tmp_path)

    class MissingRunner:
        def run(self, args, *, cwd=None, timeout=None, env=None):
            return CommandResult(args=[str(a) for a in args], returncode=127, not_found=True)

    report = run_harden(ws, top="uart_top", runner=MissingRunner(), stage="PNR")

    assert report.stage == "PNR"
    assert "librelane not available" in report.errors
    assert report.tapeout_ready is False


def test_run_harden_autodetects_top(tmp_path: Path) -> None:
    ws = ensure_workspace("task-auto", tmp_path)
    (ws / "rtl" / "leaf.v").write_text("module leaf(input a, output b); assign b=a; endmodule\n")
    (ws / "rtl" / "chip_top.v").write_text(
        "module chip_top(input clk); leaf u(.a(clk), .b()); endmodule\n"
    )
    runner = FakeHardenRunner(produce_gds=False)
    report = run_harden(ws, runner=runner, stage="SYNTH")
    assert report.top == "chip_top"


def test_run_harden_defaults_use_slang_false_for_plain_verilog(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    runner = FakeHardenRunner(produce_gds=True, clean=True)

    run_harden(ws, top="uart_top", runner=runner, stage="SYNTH")

    cfg = json.loads((ws / "exports" / "harden" / "chip" / "config.json").read_text())
    assert cfg["USE_SLANG"] is False


def test_run_harden_disables_slang_when_plugin_missing(tmp_path: Path, monkeypatch) -> None:
    ws = ensure_workspace("task-sv", tmp_path)
    (ws / "rtl" / "uart_top.sv").write_text(
        "module uart_top(input logic clk, input logic rst, output logic q);\n"
        "  always_ff @(posedge clk) q <= rst;\n"
        "endmodule\n"
    )
    monkeypatch.setattr("toolchain.harden_runner._slang_plugin_exists", lambda: False)
    runner = FakeHardenRunner(produce_gds=True, clean=True)

    run_harden(ws, top="uart_top", runner=runner, stage="SYNTH")

    cfg = json.loads((ws / "exports" / "harden" / "chip" / "config.json").read_text())
    log = (ws / "logs" / "librelane.log").read_text()
    assert cfg["USE_SLANG"] is False
    assert "slang.so not found, disabling USE_SLANG (fallback mode)" in log


def test_a_requested_top_that_names_no_module_falls_back_to_the_structural_top(
    tmp_path: Path,
) -> None:
    """spec.json's top_module is the slugified TASK NAME. When GOLDEN_GEN names
    the top itself the two diverge, and passing the slug to LibreLane produced
    `Module `<slug>' not found!` after a full elaboration — surfaced only as the
    generic "no GDS produced"."""
    from toolchain.harden_runner import pick_top, _parse_rtl

    rtl = tmp_path / "rtl"
    rtl.mkdir(parents=True)
    (rtl / "pe.v").write_text("module pe(input clk); endmodule\n")
    (rtl / "top.v").write_text(
        "module nano_cgra_sobel_top(input clk);\n  pe u(.clk(clk));\nendmodule\n")

    declared = _parse_rtl(rtl)["defs"]
    assert "nano_cgra_3x3_for_sobel_accelerator" not in declared
    assert pick_top(rtl) == "nano_cgra_sobel_top"


def test_the_clock_period_comes_from_the_designs_own_params(tmp_path: Path) -> None:
    """Nothing propagates a clock target from the spec, so hardening fell back
    to 10 ns and closed a 50 MHz design at 100 MHz — hours of OpenROAD chasing
    timing that was never required."""
    from toolchain.harden_runner import design_clock_period_ns

    (tmp_path / "rtl").mkdir(parents=True)
    (tmp_path / "rtl" / "params.vh").write_text(
        "`define CLK_FREQ    50_000_000\n`define BAUD_RATE   115_200\n")

    assert design_clock_period_ns(tmp_path) == 20.0


def test_the_golden_contract_supplies_the_clock_when_no_header_does(tmp_path: Path) -> None:
    from toolchain.harden_runner import design_clock_period_ns

    (tmp_path / "rtl").mkdir(parents=True)
    (tmp_path / "context").mkdir(parents=True)
    (tmp_path / "context" / "golden_contract.md").write_text(
        "| param | value | meaning |\n| CLK_FREQ | 25_000_000 | 25 MHz system clock |\n")

    assert design_clock_period_ns(tmp_path) == 40.0


def test_an_implausible_clock_is_ignored(tmp_path: Path) -> None:
    # A bad parse must not drive the whole flow; the caller falls back to 10 ns.
    from toolchain.harden_runner import design_clock_period_ns

    (tmp_path / "rtl").mkdir(parents=True)
    (tmp_path / "rtl" / "params.vh").write_text("`define CLK_FREQ 50\n")

    assert design_clock_period_ns(tmp_path) == 0.0


def test_no_clock_declared_anywhere_is_not_an_error(tmp_path: Path) -> None:
    from toolchain.harden_runner import design_clock_period_ns

    (tmp_path / "rtl").mkdir(parents=True)
    assert design_clock_period_ns(tmp_path) == 0.0


def test_live_progress_reports_the_current_librelane_step(tmp_path: Path) -> None:
    """LibreLane writes its log only at the end, so a multi-hour harden showed a
    single static line and the UI looked hung."""
    import time as _time
    from toolchain.harden_runner import _live_progress_text

    chip = tmp_path / "chip"
    run = chip / "runs" / "RUN_2026-08-06_05-32-45"
    for name in ("01-verilator-lint", "02-yosys-synthesis", "39-openroad-globalrouting"):
        (run / name).mkdir(parents=True)
    (run / "flow.log").write_text("Running 'OpenROAD.GlobalRouting'…\nLogging subprocess…\n")

    text = _live_progress_text(chip, "SYNTH", 1, 20.0, 35, _time.time())

    assert "IN PROGRESS" in text
    assert "clock 20.0 ns" in text
    assert "3 steps completed" in text
    assert "CURRENT STEP: 39-openroad-globalrouting" in text
    assert "OpenROAD.GlobalRouting" in text


def test_live_progress_before_librelane_starts_is_not_an_error(tmp_path: Path) -> None:
    import time as _time
    from toolchain.harden_runner import _live_progress_text

    text = _live_progress_text(tmp_path / "chip", "SYNTH", 1, 20.0, 35, _time.time())
    assert "waiting for LibreLane to start" in text


def _coherence_error(declared_ns: float, closed_ns: float) -> str:
    """The gate's condition, mirrored so the test states the rule directly."""
    return "" if closed_ns <= declared_ns + 0.01 else "clock coherence"


def test_closing_slower_than_the_design_assumes_is_an_error() -> None:
    # 50 MHz design (BIT_TICKS = 434 = 50e6/115200) hardened at 40.4 MHz: the
    # UART would transmit at ~93k baud. Every other stage stays green because
    # SIM checks the RTL against a golden model that assumes the same 50 MHz.
    assert _coherence_error(20.0, 24.73) == "clock coherence"


def test_closing_at_or_above_the_declared_clock_is_fine() -> None:
    assert _coherence_error(20.0, 20.0) == ""
    assert _coherence_error(20.0, 18.0) == ""


# --------------------------------------------------------------------------- #
# Hollow-chip gate. A `reg [7:0] mem [0:1023]` that nothing observable depends
# on is deleted by yosys; the empty design then hardens, passes every
# downstream check and reaches EXPORT carrying no accelerator at all.
# --------------------------------------------------------------------------- #
def _synth_run(tmp_path: Path, flop_lines: str) -> Path:
    run = tmp_path / "runs" / "RUN_1" / "06-yosys-synthesis" / "reports"
    run.mkdir(parents=True)
    (run / "stat.rpt").write_text(flop_lines)
    return tmp_path / "runs" / "RUN_1"


def test_declared_memory_arrays_are_counted(tmp_path: Path) -> None:
    from toolchain.harden_runner import declared_storage_bits

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "ram.v").write_text(
        "module r;\n  reg [7:0] img_ram [0:1023];\n  reg [7:0] result_ram [0:899];\n"
        "  reg [2:0] state;\n endmodule\n")

    bits = declared_storage_bits(rtl)
    assert bits["ram.v:img_ram"] == 8192
    assert bits["ram.v:result_ram"] == 7200
    assert "ram.v:state" not in bits          # a scalar reg is not storage


def test_memory_optimized_away_is_flagged(tmp_path: Path) -> None:
    from toolchain.harden_runner import storage_vanished

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "ram.v").write_text("module r;\n  reg [7:0] in_mem [0:1023];\nendmodule\n")
    run = _synth_run(tmp_path, "      91 6.79E+03   gf180mcu_fd_sc_mcu7t5v0__dffrnq_1\n")

    vanished, why = storage_vanished(rtl, run)
    assert vanished
    assert "optimized away" in why
    assert "8192 bits" in why


def test_memory_that_survived_is_not_flagged(tmp_path: Path) -> None:
    from toolchain.harden_runner import storage_vanished

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "ram.v").write_text("module r;\n  reg [7:0] img_ram [0:1023];\nendmodule\n")
    run = _synth_run(tmp_path, "    8192 9.81E+05   gf180mcu_fd_sc_mcu7t5v0__dffq_1\n")

    assert storage_vanished(rtl, run)[0] is False


def test_a_design_with_no_memory_is_not_flagged(tmp_path: Path) -> None:
    from toolchain.harden_runner import storage_vanished

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "pe.v").write_text("module pe;\n  reg [7:0] acc;\nendmodule\n")
    run = _synth_run(tmp_path, "      12 1.0   gf180mcu_fd_sc_mcu7t5v0__dffq_1\n")

    assert storage_vanished(rtl, run)[0] is False


def test_an_unreadable_stat_report_does_not_fire_the_gate(tmp_path: Path) -> None:
    # Unknown must never be treated as zero — that would fail every run whose
    # report layout differs.
    from toolchain.harden_runner import storage_vanished, synthesized_flop_count

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "ram.v").write_text("module r;\n  reg [7:0] m [0:1023];\nendmodule\n")
    empty = tmp_path / "runs" / "RUN_1"
    empty.mkdir(parents=True)

    assert synthesized_flop_count(empty) == -1
    assert storage_vanished(rtl, empty)[0] is False


def test_rtl_changed_after_sim_is_detectable(tmp_path: Path) -> None:
    """RTL_REPAIR rewrites rtl/ between SIM and SYNTH and nothing re-runs SIM,
    so the GDS was built from code that never passed simulation."""
    from toolchain.sim_runner import rtl_fingerprint

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "a.v").write_text("module a; endmodule\n")
    verified = rtl_fingerprint(rtl)

    assert rtl_fingerprint(rtl) == verified          # unchanged -> same stamp
    (rtl / "a.v").write_text("module a; wire x; endmodule\n")
    assert rtl_fingerprint(rtl) != verified          # repaired -> different


def test_the_fingerprint_covers_headers_too(tmp_path: Path) -> None:
    from toolchain.sim_runner import rtl_fingerprint

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "a.v").write_text("module a; endmodule\n")
    (rtl / "params.vh").write_text("`define W 8\n")
    before = rtl_fingerprint(rtl)

    (rtl / "params.vh").write_text("`define W 16\n")   # a macro change IS a design change
    assert rtl_fingerprint(rtl) != before


def test_tune_state_is_discarded_when_the_rtl_changes(tmp_path: Path) -> None:
    """A clock relaxed to 127.95 ns for a 70k-instance design was handed
    straight to its 10x smaller replacement, which then hardened at 7.8 MHz."""
    import json
    from toolchain.harden_runner import _rtl_fingerprint

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "a.v").write_text("module a; endmodule\n")
    fp_before = _rtl_fingerprint(rtl)

    state = {"rtl_fingerprint": fp_before, "clock_period": 127.95}
    assert state["rtl_fingerprint"] == _rtl_fingerprint(rtl)      # reused

    (rtl / "a.v").write_text("module a; wire x; endmodule\n")     # design replaced
    assert state["rtl_fingerprint"] != _rtl_fingerprint(rtl)      # discarded


# --------------------------------------------------------------------------- #
# A reg driven from two always blocks simulates fine (iverilog: last NBA wins,
# so SIM passed 900/900) and cannot synthesise. Yosys logs one conflict PER BIT,
# ERROR_ON_SYNTH_CHECKS is off, and the netlist collapsed to a single tie cell —
# surfacing only as "[PDN-0185] Insufficient width (4.48 um) to add straps".
# --------------------------------------------------------------------------- #
def _yosys_run(tmp_path, text: str):
    step = tmp_path / "06-yosys-synthesis"
    step.mkdir(parents=True)
    (step / "yosys-synthesis.log").write_text(text)
    return tmp_path


def test_per_bit_conflicts_collapse_to_one_signal_name(tmp_path) -> None:
    from toolchain.harden_runner import _multi_driver_conflicts

    log = "\n".join(
        f"Warning: multiple conflicting drivers for uart_tx.\\baud_cnt [{b}]:" for b in range(32)
    )
    assert _multi_driver_conflicts(_yosys_run(tmp_path, log)) == ["uart_tx.baud_cnt"]


def test_several_conflicting_signals_are_all_reported(tmp_path) -> None:
    from toolchain.harden_runner import _multi_driver_conflicts

    log = ("Warning: multiple conflicting drivers for uart_tx.\\baud_cnt [0]:\n"
           "Warning: multiple conflicting drivers for ctrl.\\state [1]:\n")
    found = _multi_driver_conflicts(_yosys_run(tmp_path, log))
    assert set(found) == {"uart_tx.baud_cnt", "ctrl.state"}


def test_a_clean_synthesis_log_reports_no_conflicts(tmp_path) -> None:
    from toolchain.harden_runner import _multi_driver_conflicts

    assert _multi_driver_conflicts(_yosys_run(tmp_path, "Removed a total of 0 cells.\n")) == []


# --------------------------------------------------------------------------- #
# Two settings made hardening slow rather than wrong. design_clock_period_ns()
# existed for exactly this and was only ever used to REPORT the number, so the
# run kept the naive 10 ns (100 MHz) default while params.vh declared 50 MHz;
# and the nom-only RC restriction sat INSIDE the 3.3V branch, so 5v0 swept all
# nine corners. Together: ResizerTimingPostCTS took 28 of a 53-minute run.
# --------------------------------------------------------------------------- #
def test_five_volt_runs_are_restricted_to_the_three_nominal_corners() -> None:
    from toolchain.harden_runner import _build_config

    cfg = _build_config(Path("rtl"), Path("src"), "top", "clk", 20.0, 35, voltage="5v0")
    corners = cfg.get("STA_CORNERS") or []
    assert len(corners) == 3, corners
    assert all(c.startswith("nom_") for c in corners), corners
    assert not any(c.startswith(("min_", "max_")) for c in corners), corners
    assert cfg["DEFAULT_CORNER"] == "nom_tt_025C_5v00"
    # LIB must stay unset at 5V so LibreLane keeps its native 5V libs.
    assert "LIB" not in cfg


def test_three_volt_three_runs_keep_their_own_nominal_corners() -> None:
    from toolchain.harden_runner import _build_config

    cfg = _build_config(Path("rtl"), Path("src"), "top", "clk", 20.0, 35, voltage="3v3")
    assert len(cfg["STA_CORNERS"]) == 3
    assert cfg["DEFAULT_CORNER"] == "nom_tt_025C_3v30"
    assert "LIB" in cfg


def test_the_declared_clock_reaches_the_librelane_config() -> None:
    from toolchain.harden_runner import _build_config

    cfg = _build_config(Path("rtl"), Path("src"), "top", "clk", 20.0, 35, voltage="5v0")
    assert cfg["CLOCK_PERIOD"] == 20.0


# --------------------------------------------------------------------------- #
# The auto-tuner relaxes from wherever it STARTS. A run that began at the wrong
# 10 ns baseline over-constrained itself, failed timing, and walked the clock
# out to 78.37 ns (12.8 MHz) — then every later run inherited that via
# max(clock, saved), hardening a 50 MHz design at a quarter speed and its UART
# at a quarter baud, which the clock-coherence gate then failed forever.
# --------------------------------------------------------------------------- #
def _tuned_workspace(tmp_path, saved_clock: float):
    import json
    (tmp_path / "rtl").mkdir(parents=True, exist_ok=True)
    (tmp_path / "rtl" / "params.vh").write_text("`define CLK_FREQ 50_000_000\n")
    (tmp_path / "rtl" / "top.v").write_text("module top(input clk); endmodule\n")
    harden = tmp_path / "exports" / "harden"
    harden.mkdir(parents=True, exist_ok=True)
    from toolchain.harden_runner import _rtl_fingerprint
    (harden / ".tune_state.json").write_text(json.dumps({
        "rtl_fingerprint": _rtl_fingerprint(tmp_path / "rtl"),
        "clock_period": saved_clock, "core_util": 35, "density_bump": 0, "extra_cfg": {},
    }))
    return tmp_path


def test_a_stale_slower_clock_is_not_inherited(tmp_path) -> None:
    from toolchain.harden_runner import design_clock_period_ns

    ws = _tuned_workspace(tmp_path, 78.37)
    # The design declares 50 MHz = 20 ns; the persisted 78.37 ns must not win.
    assert design_clock_period_ns(ws) == 20.0
    import json
    saved = json.loads((ws / "exports" / "harden" / ".tune_state.json").read_text())
    assert saved["clock_period"] > design_clock_period_ns(ws)  # the trap this guards


def test_the_declared_clock_is_read_from_params(tmp_path) -> None:
    from toolchain.harden_runner import design_clock_period_ns

    ws = _tuned_workspace(tmp_path, 20.0)
    assert design_clock_period_ns(ws) == 20.0
