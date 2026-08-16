from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.stage_handlers import StageContext, dispatch


def _ctx(tmp_path: Path, stage: str, **kwargs) -> StageContext:
    workspace = tmp_path
    for sub in ("rtl", "tb", "reports", "waves", "gds", "spec", "plans", "exports", "golden", "logs"):
        (workspace / sub).mkdir(parents=True, exist_ok=True)
    return StageContext(task_id="task-42", stage=stage, workspace=workspace, **kwargs)


def test_spec_ingest_writes_structured_spec(tmp_path: Path) -> None:
    sc = _ctx(tmp_path, "SPEC_INGEST", prompt="Build a 32-bit register", context={"task_name": "reg32"})
    result = dispatch(sc)

    assert result.agent_name == "SpecInterpreter"
    assert "spec/spec.json" in result.workspace_files
    spec = json.loads((tmp_path / "spec/spec.json").read_text())
    assert spec["task_id"] == "task-42"
    assert result.structured_conclusion["top_module"]


def test_rtl_gen_writes_top_module(tmp_path: Path) -> None:
    sc = _ctx(tmp_path, "RTL_GEN", context={"top_module": "alu"})
    result = dispatch(sc)

    assert result.agent_name == "RTLAuthor"
    assert (tmp_path / "rtl/alu.v").is_file()
    assert (tmp_path / "reports/rtl_architecture.md").is_file()


def test_golden_gen_writes_runnable_model_and_passing_tests(tmp_path: Path) -> None:
    sc = _ctx(tmp_path, "GOLDEN_GEN", context={"top_module": "accel"})
    result = dispatch(sc)

    assert result.agent_name == "GoldenModeler"
    assert (tmp_path / "golden/model/accel.py").is_file()
    assert (tmp_path / "golden/tests/test_accel.py").is_file()
    assert (tmp_path / "context/golden_contract.md").is_file()

    # The stage RUNS the golden suite itself rather than trusting a self-report.
    tests = json.loads((tmp_path / "golden/test_results.json").read_text())
    assert tests["ran"] is True
    assert tests["passed"] >= 1 and tests["failed"] == 0

    # Exported vectors are what TB_GEN turns into per-module testbenches.
    vectors = json.loads((tmp_path / "golden/vectors/accel.json").read_text())
    assert vectors["module"] == "accel"
    assert vectors["vectors"]

    summary = json.loads((tmp_path / "golden/golden_summary.json").read_text())
    assert summary["top"] == "accel"
    assert result.structured_conclusion["awaiting_review"] is True


def test_tb_gen_writes_self_checking_testbench(tmp_path: Path) -> None:
    sc = _ctx(tmp_path, "TB_GEN", context={"top_module": "alu"})
    result = dispatch(sc)

    assert result.agent_name == "Verifier"
    tb = (tmp_path / "tb/alu_tb.v").read_text()
    assert "$dumpfile" in tb
    assert "alu dut" in tb


def test_signoff_reads_eda_reports(tmp_path: Path) -> None:
    report = {
        "stage": "DRC_LVS",
        "metrics": {"wns_ns": 0.12},
        "signoff": {"failed": []},
        "tapeout_ready": True,
    }
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports/drc_lvs_report.json").write_text(json.dumps(report))

    sc = _ctx(tmp_path, "SIGNOFF", context={"task_name": "alu"})
    result = dispatch(sc)

    assert result.structured_conclusion["tapeout_ready"] is True
    assert (tmp_path / "reports/signoff_summary.md").is_file()


def test_unknown_stage_uses_fallback(tmp_path: Path) -> None:
    sc = _ctx(tmp_path, "SYNTH", context={"agent_name": "Diagnoser"})
    result = dispatch(sc)

    assert result.agent_name == "Diagnoser"
    assert "reports/synth_notes.md" in result.workspace_files
    assert result.recommended_next == "Confirm orchestrator approval and continue the remaining DAG."


# --------------------------------------------------------------------------- #
# Picking UART for I/O is a user-level choice; knowing what it implies for
# on-chip buffering is the flow's job. Without this the model reaches for the
# software shape (load frame -> compute -> dump frame) and buries two frames in
# flip-flops: 15,671 DFFs and a 5.18 mm2 die for a few hundred gates of compute.
# --------------------------------------------------------------------------- #
class _BriefCtx:
    def __init__(self, brief: str) -> None:
        self.design_brief = brief


def test_serial_io_triggers_the_streaming_architecture_rule() -> None:
    from agents.stage_handlers import _streaming_io_note

    note = _streaming_io_note(_BriefCtx("sobel accelerator, for input output use UART"))
    assert "STREAM, DO NOT BUFFER THE DATASET" in note
    assert "LINE BUFFERS" in note


def test_a_parallel_bus_design_gets_no_streaming_rule() -> None:
    from agents.stage_handlers import _streaming_io_note

    assert _streaming_io_note(_BriefCtx("a 3x3 sobel filter with a parallel pixel bus")) == ""


def test_serial_io_without_a_window_operator_omits_the_line_buffer_clause() -> None:
    # The line-buffer sizing only makes sense for a sliding-window operator;
    # the general "don't buffer the dataset" rule still applies.
    from agents.stage_handlers import _streaming_io_note

    note = _streaming_io_note(_BriefCtx("a UART loopback with a CRC block"))
    assert note and "LINE BUFFERS" not in note
    assert "AS SOON AS IT IS COMPUTED" in note


def test_the_rule_warns_about_memory_that_synthesis_deletes() -> None:
    from agents.stage_handlers import _streaming_io_note

    note = _streaming_io_note(_BriefCtx("sobel over UART"))
    assert "deleted by synthesis" in note


# --------------------------------------------------------------------------- #
# The brief is not the design. "nano cgra 3x3 sobel accelerator v2" names no
# interface, PLAN gave it a UART anyway, and keying the rule off the brief alone
# left both the advice and the frame-buffer gate switched off for the whole run:
# `frame [0:1023]` + `out_buf [0:1023]` = 16,384 DFFs on a 7.56 mm2 die.
# --------------------------------------------------------------------------- #
class _DesignCtx:
    def __init__(self, brief: str, workspace) -> None:
        self.design_brief = brief
        self.workspace = workspace


def test_a_uart_in_the_rtl_triggers_the_rule_even_when_the_brief_is_silent(tmp_path) -> None:
    from agents.stage_handlers import _streaming_io_note

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "uart_rx.v").write_text("module uart_rx(input clk); endmodule\n")
    (rtl / "sobel_core.v").write_text("module sobel_core(input clk); endmodule\n")

    note = _streaming_io_note(_DesignCtx("nano cgra 3x3 sobel accelerator v2", tmp_path))
    assert "STREAM, DO NOT BUFFER THE DATASET" in note
    assert "LINE BUFFERS" in note


def test_a_design_with_no_serial_block_anywhere_still_gets_no_rule(tmp_path) -> None:
    from agents.stage_handlers import _streaming_io_note

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "sobel_core.v").write_text("module sobel_core(input clk); endmodule\n")

    assert _streaming_io_note(_DesignCtx("nano cgra 3x3 sobel accelerator v2", tmp_path)) == ""


# --------------------------------------------------------------------------- #
# The GOLDEN gate asks "is this output correct?". A model failing its OWN tests
# cannot answer that: RTL_GEN would faithfully build hardware reproducing the
# wrong numbers, and SIM would pass because it checks the RTL against this same
# broken reference. 9/32 failing tests reached a human gate twice.
# --------------------------------------------------------------------------- #
class _GoldenCtx:
    def __init__(self, workspace) -> None:
        self.workspace = workspace
        self.design_brief = "sobel over UART"


def test_failing_assertions_are_pasted_into_the_repair_prompt(tmp_path) -> None:
    from agents.stage_handlers import _golden_test_failures

    (tmp_path / "golden").mkdir(parents=True)
    (tmp_path / "golden" / "test_log.txt").write_text(
        "..F...F\n"
        "E       assert -112 == 400\n"
        "FAILED golden/tests/test_pe_mac.py::test_large_accumulate - assert -112 == 400\n"
        "FAILED golden/tests/test_uart_rx.py::test_valid_pulse - assert 0 == 1\n")

    detail = _golden_test_failures(_GoldenCtx(tmp_path))
    assert "test_pe_mac.py::test_large_accumulate" in detail
    assert "assert -112 == 400" in detail


def test_no_test_log_yields_no_detail(tmp_path) -> None:
    from agents.stage_handlers import _golden_test_failures

    assert _golden_test_failures(_GoldenCtx(tmp_path)) == ""


def test_a_flat_ip_only_manifest_is_reported_as_a_gap(tmp_path) -> None:
    # Every block "ip", no top: RTL_GEN's structure gate has nothing to enforce.
    import json
    from agents.stage_handlers import _golden_gaps

    (tmp_path / "golden" / "model").mkdir(parents=True)
    (tmp_path / "golden" / "model" / "pe.py").write_text("x = 1\n")
    (tmp_path / "golden" / "tests").mkdir(parents=True)
    (tmp_path / "golden" / "tests" / "test_pe.py").write_text("def test_x(): assert True\n")
    (tmp_path / "golden" / "golden_summary.json").write_text(json.dumps(
        {"top": "chip", "ips": [{"name": n, "tier": "ip", "role": ""}
                                for n in ("a", "b", "c", "d", "e")]}))

    gaps = _golden_gaps(_GoldenCtx(tmp_path), {"ran": True, "passed": 1, "failed": 0}, False)
    joined = " ".join(gaps)
    assert "no module is tagged" in joined
    assert "needs a one-line `role`" in joined


def test_a_testbench_naming_a_port_the_dut_lacks_fails_elaboration(tmp_path) -> None:
    """write_file_disk checks a tb with `-i`, which never elaborates the DUT
    instantiation — so a wrong port name was written 'clean' and only surfaced
    at SIM as `port ``data_i'' is not a port of dut`."""
    from verilog_check import elaborate_tb

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "dut.v").write_text(
        "module dut(input clk, input rst_n, output reg done);\n"
        "  always @(posedge clk) done <= rst_n;\nendmodule\n")
    tb = tmp_path / "tb"
    tb.mkdir()
    (tb / "bad_tb.v").write_text(
        "module bad_tb;\n reg clk=0; wire done;\n"
        " dut u(.clk(clk), .data_i(1'b0), .done(done));\nendmodule\n")

    err = elaborate_tb(tb / "bad_tb.v", rtl)
    assert err == "" or "data_i" in err   # '' only when iverilog is absent


def test_a_correct_testbench_elaborates_clean(tmp_path) -> None:
    from verilog_check import elaborate_tb

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "dut.v").write_text(
        "module dut(input clk, input rst_n, output reg done);\n"
        "  always @(posedge clk) done <= rst_n;\nendmodule\n")
    tb = tmp_path / "tb"
    tb.mkdir()
    (tb / "good_tb.v").write_text(
        "module good_tb;\n reg clk=0; reg rst_n=0; wire done;\n"
        " dut u(.clk(clk), .rst_n(rst_n), .done(done));\nendmodule\n")

    assert elaborate_tb(tb / "good_tb.v", rtl) == ""


def test_the_dumpfile_check_requires_the_name_sim_actually_collects() -> None:
    """sim_runner collects waves/design.vcd. A tb dumping to its own filename
    left the run with no waveform while the old `"$dumpfile" not in text` check
    happily passed it."""
    import re

    pattern = r'\$dumpfile\s*\(\s*"(\./)?(waves/)?design\.vcd"'
    assert re.search(pattern, '$dumpfile("design.vcd");')
    assert re.search(pattern, '$dumpfile("waves/design.vcd");')
    assert not re.search(pattern, '$dumpfile("nano_cgra_3x3_sobel_accelerator_v2.vcd");')
    assert not re.search(pattern, '$dumpfile("waves/my_top.vcd");')


# --------------------------------------------------------------------------- #
# Closing the clock loop. A 50 MHz design that hardens at 13.9 MHz still carries
# BIT_TICKS computed for 50 MHz — the chip's UART would run at ~32k baud, not
# 115200. The achieved clock has to come back to the stages that derive those
# constants, or the flow just dead-ends on the mismatch.
# --------------------------------------------------------------------------- #
def test_the_achieved_clock_is_fed_back_to_the_generator(tmp_path) -> None:
    import json
    from agents.stage_handlers import _achieved_clock_note

    (tmp_path / "context").mkdir(parents=True)
    (tmp_path / "context" / "achieved_clock.json").write_text(json.dumps(
        {"clock_period_ns": 71.94, "clock_mhz": 13.901, "clock_hz": 13900472}))

    note = _achieved_clock_note(_GoldenCtx(tmp_path))
    assert "13.9" in note
    assert "CLK_FREQ = 13900472" in note
    assert "BIT_TICKS" in note


def test_no_achieved_clock_yet_means_no_note(tmp_path) -> None:
    from agents.stage_handlers import _achieved_clock_note

    assert _achieved_clock_note(_GoldenCtx(tmp_path)) == ""


def test_a_nonsense_achieved_clock_is_ignored(tmp_path) -> None:
    import json
    from agents.stage_handlers import _achieved_clock_note

    (tmp_path / "context").mkdir(parents=True)
    (tmp_path / "context" / "achieved_clock.json").write_text(json.dumps(
        {"clock_period_ns": 0, "clock_hz": 0}))

    assert _achieved_clock_note(_GoldenCtx(tmp_path)) == ""


def test_a_parameterised_frame_buffer_is_detected(tmp_path) -> None:
    """`reg [7:0] frame [0:N*N-1]` with `localparam N = `IMG_N` and
    `define IMG_N 32 read as ZERO bits to a numeric-only scan, so an 8192-bit
    frame store passed as a streaming design."""
    from verilog_check import frame_buffer_violations, memory_arrays

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "params.vh").write_text("`define IMG_N 32\n")
    (rtl / "window_gen.v").write_text(
        '`include "params.vh"\nmodule window_gen;\n'
        "  localparam N = `IMG_N;\n"
        "  reg [7:0] frame [0:N*N-1];\n"
        "  reg [7:0] buf0 [0:N-1];\nendmodule\n")

    bits = {name: b for _, name, _, b in memory_arrays(rtl)}
    assert bits["frame"] == 8192
    assert bits["buf0"] == 256

    bad = frame_buffer_violations(rtl)
    assert any("frame" in v and "1024 entries" in v for v in bad)
    assert not any("buf0" in v for v in bad)   # a line buffer is fine


def test_line_buffers_alone_are_not_a_violation(tmp_path) -> None:
    from verilog_check import frame_buffer_violations

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "line_buffer.v").write_text(
        "module line_buffer;\n  localparam W = 32;\n"
        "  reg [7:0] buf0 [0:W-1];\n  reg [7:0] buf1 [0:W-1];\n"
        "  reg [7:0] buf2 [0:W-1];\nendmodule\n")

    assert frame_buffer_violations(rtl) == []


def test_a_testbench_poking_inside_the_dut_is_flagged() -> None:
    """The 200x200 chip passed SIM this way: the tb wrote the image straight
    into u_ram.in_mem and read it back from out_mem, so the pins were never
    exercised, synthesis deleted the memory and the chip shipped empty."""
    from verilog_check import hierarchical_dut_access

    tb = ("module t;\n"
          "  initial begin\n"
          "    u_top.u_ram.in_mem[i] = img_mem[i];\n"
          "    out_buf[i] = u_top.u_ram.out_mem[i];\n"
          "  end\nendmodule\n")

    hits = hierarchical_dut_access(tb)
    assert any("in_mem" in h for h in hits)


def test_a_port_driven_testbench_is_clean() -> None:
    from verilog_check import hierarchical_dut_access

    tb = ("module t;\n reg clk, rx; wire tx;\n"
          " dut u(.clk(clk), .rx(rx), .tx(tx));\n"
          " initial begin rx <= 1'b0; #10 rx <= 1'b1; end\nendmodule\n")

    assert hierarchical_dut_access(tb) == []


def test_forcing_an_internal_signal_is_flagged() -> None:
    from verilog_check import hierarchical_dut_access

    assert hierarchical_dut_access("module t;\n initial force u_ctrl.pixel_idx = 5;\nendmodule\n")


def test_excluded_tools_are_withheld(tmp_path) -> None:
    """Prose does not stop a model reading: a pass told 'do NOT open the file,
    write from scratch' read it 2, then 6, then 12 times and never once wrote.
    Withholding the read tools leaves only the action the pass exists for.

    Exercises the filter build_step_agent applies, without needing a provider."""
    from agents.deep_agent import make_fs_tools

    tools = list(make_fs_tools(tmp_path))
    names = {getattr(t, "name", "") for t in tools}
    assert "read_file_disk" in names and "write_file_disk" in names

    drop = {"read_file_disk", "grep_files", "run_python"}
    kept = {getattr(t, "name", "") for t in tools
            if getattr(t, "name", "") not in drop}
    assert "read_file_disk" not in kept
    assert "write_file_disk" in kept


# --------------------------------------------------------------------------- #
# The gate shows waves/golden_output.mem as ground truth. Repair rounds rewrite
# the model but not the dump, so a repaired model can be presented with the
# broken model's picture — 838 of 900 pixels stale in one run.
# --------------------------------------------------------------------------- #
def _golden_ws(tmp_path, mem_first: bool):
    import os, time
    (tmp_path / "golden" / "model").mkdir(parents=True)
    (tmp_path / "golden" / "tests").mkdir(parents=True)
    (tmp_path / "waves").mkdir()
    dump = tmp_path / "waves" / "golden_output.mem"
    model = tmp_path / "golden" / "model" / "top.py"
    first, second = (dump, model) if mem_first else (model, dump)
    first.write_text("x\n")
    os.utime(first, (1_000_000, 1_000_000))
    second.write_text("y\n")
    os.utime(second, (2_000_000, 2_000_000))
    return tmp_path


def _stale_gap(gaps):
    return [g for g in gaps if "golden_output.mem is OLDER" in g]


def test_a_dump_older_than_the_model_is_reported_as_stale(tmp_path) -> None:
    from agents.stage_handlers import _golden_gaps

    ws = _golden_ws(tmp_path, mem_first=True)   # dump written BEFORE the repair
    gaps = _golden_gaps(_DesignCtx("sobel over UART", ws), {"ran": True, "passed": 52}, False)
    assert _stale_gap(gaps), "a pre-repair dump must be flagged before the human gate"


def test_a_dump_newer_than_the_model_is_accepted(tmp_path) -> None:
    from agents.stage_handlers import _golden_gaps

    ws = _golden_ws(tmp_path, mem_first=False)  # dump re-written AFTER the repair
    gaps = _golden_gaps(_DesignCtx("sobel over UART", ws), {"ran": True, "passed": 52}, False)
    assert not _stale_gap(gaps)


# --------------------------------------------------------------------------- #
# `define/`MACRO bounds are this codebase's own idiom (params.vh). _sb_eval
# substituted the macro NAME but left the BACKTICK ("`32-1"), the digits-only
# guard rejected it, and the array vanished — so frame_buffer_violations called
# a design clean without having parsed a single one of its arrays.
# --------------------------------------------------------------------------- #
def test_a_macro_bounded_frame_buffer_is_detected(tmp_path) -> None:
    from verilog_check import frame_buffer_violations, memory_arrays

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "params.vh").write_text(
        "`define CLK_FREQ 32'd50_000_000\n`define DATA_W 8\n`define IMG_PIXELS 1024\n")
    (rtl / "framestore.v").write_text(
        "module framestore(input clk);\n"
        "    reg [`DATA_W-1:0] frame [0:`IMG_PIXELS-1];\n"
        "endmodule\n")

    arrays = memory_arrays(rtl)
    assert arrays, "a macro-bounded array must be parsed, not silently skipped"
    assert arrays[0][2] == 1024 and arrays[0][3] == 8192
    assert any("frame" in v for v in frame_buffer_violations(rtl))


def test_a_macro_bounded_line_buffer_stays_clean(tmp_path) -> None:
    # The streaming shape must NOT trip the gate: one row, not one frame.
    from verilog_check import frame_buffer_violations, memory_arrays

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "params.vh").write_text("`define DATA_W 8\n`define LINE_BUF_W 32\n")
    (rtl / "line_buffer.v").write_text(
        "module line_buffer(input clk);\n"
        "    reg [`DATA_W-1:0] mem [0:`LINE_BUF_W-1];\n"
        "endmodule\n")

    assert memory_arrays(rtl)[0][2] == 32
    assert frame_buffer_violations(rtl) == []


def test_sized_literals_resolve_to_their_value_not_their_width() -> None:
    # `define BAUD_DIV 32'd434 used to resolve to 32, and `define ADDR 8'h80 to
    # 8 — every sized macro became a small wrong number, under-counting any
    # array bounded by one.
    from verilog_check import _sb_int

    assert _sb_int("32'd434") == 434
    assert _sb_int("32'd50_000_000") == 50_000_000
    assert _sb_int("8'h80") == 128
    assert _sb_int("4'b1010") == 10
    assert _sb_int("1024") == 1024
    assert _sb_int("not_a_number") is None


def test_one_unparseable_define_does_not_drop_the_rest_of_the_header(tmp_path) -> None:
    from verilog_check import frame_buffer_violations

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "params.vh").write_text(
        "`define WEIRD 72'hDEAD_BEEF_CAFE\n"      # not a plain constant
        "`define DATA_W 8\n`define IMG_PIXELS 1024\n")
    (rtl / "framestore.v").write_text(
        "module framestore(input clk);\n"
        "    reg [`DATA_W-1:0] frame [0:`IMG_PIXELS-1];\n"
        "endmodule\n")

    assert any("frame" in v for v in frame_buffer_violations(rtl))


# --------------------------------------------------------------------------- #
# The frame-buffer gate ran only at RTL_GEN, so a repair could quietly undo it:
# fixing a serial off-by-one, the agent added `result_q [0:255]` (2048 DFFs,
# ~40% of cell area) to absorb a backlog it measured at ~90 entries.
# --------------------------------------------------------------------------- #
def test_a_buffer_reintroduced_by_a_repair_is_caught(tmp_path) -> None:
    from agents.stage_handlers import _rtl_structure_gaps

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "params.vh").write_text("`define DATA_W 8\n`define QDEPTH 256\n")
    (rtl / "uart_tx.v").write_text("module uart_tx(input clk); endmodule\n")
    (rtl / "nano_controller.v").write_text(
        "module nano_controller(input clk);\n"
        "    reg [`DATA_W-1:0] result_q [0:`QDEPTH-1];\n"
        "endmodule\n")

    ctx = _DesignCtx("nano cgra sobel accelerator", tmp_path)
    gaps = _rtl_structure_gaps(ctx, {"files": ["uart_tx.v", "nano_controller.v"]})
    assert any("result_q" in g and "FRAME BUFFER" in g.upper() for g in gaps), gaps


def test_a_streaming_repair_result_passes_the_regression_check(tmp_path) -> None:
    from agents.stage_handlers import _rtl_structure_gaps

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "params.vh").write_text("`define DATA_W 8\n`define LINE_BUF_W 32\n")
    (rtl / "uart_tx.v").write_text("module uart_tx(input clk); endmodule\n")
    (rtl / "line_buffer.v").write_text(
        "module line_buffer(input clk);\n"
        "    reg [`DATA_W-1:0] mem [0:`LINE_BUF_W-1];\n"
        "endmodule\n")

    ctx = _DesignCtx("nano cgra sobel accelerator", tmp_path)
    gaps = _rtl_structure_gaps(ctx, {"files": ["uart_tx.v", "line_buffer.v"]})
    assert not any("FRAME BUFFER" in g.upper() for g in gaps), gaps


# --------------------------------------------------------------------------- #
# "the RTL CHANGED after SIM verified it" is a PROCESS condition — resolved by
# re-running SIM. Handing it to the repair agent makes it edit working RTL,
# which changes the fingerprint and re-raises the same error: an endless
# repair/harden loop that presents as "it always fails".
# --------------------------------------------------------------------------- #
def test_process_conditions_never_trigger_an_rtl_repair() -> None:
    from agents.stage_handlers import _NON_RTL_SYNTH_ERROR_RE as R

    for e in ["no GDS produced",
              "the RTL CHANGED after SIM verified it — hardening would build code that ...",
              "librelane not available",
              "hardening timeout",
              "no RTL modules found in workspace/rtl",
              "no synthesizable RTL files found"]:
        assert R.search(e), e


def test_real_rtl_defects_still_trigger_a_repair() -> None:
    from agents.stage_handlers import _NON_RTL_SYNTH_ERROR_RE as R

    for e in ["MULTIPLE CONFLICTING DRIVERS — uart_tx.baud_cnt is assigned from two always blocks",
              "storage declared in RTL vanished during synthesis",
              "[PDN-0185] Insufficient width (4.48 um) to add straps on layer Metal4"]:
        assert not R.search(e), e


# --------------------------------------------------------------------------- #
# A reg driven by two always blocks simulates fine and cannot synthesise. It
# passed SIM 900/900, collapsed the netlist to one tie cell, and surfaced 50
# minutes later as "[PDN-0185] Insufficient width (4.48 um)". Catch it on the
# RTL, before a testbench ever runs.
# --------------------------------------------------------------------------- #
def test_a_two_driver_register_is_caught_on_the_rtl(tmp_path) -> None:
    from verilog_check import multi_driver_regs

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "uart_tx.v").write_text(
        "module uart_tx(input clk, input rst_n, input tx_start, output reg tx_out);\n"
        "    reg [31:0] baud_cnt;\n"
        "    always @(posedge clk) begin\n"
        "        if (baud_cnt == 433) baud_cnt <= 32'd0;\n"
        "        else baud_cnt <= baud_cnt + 32'd1;\n"
        "    end\n"
        "    always @(posedge clk) begin\n"
        "        if (tx_start) begin\n"
        "            baud_cnt <= 32'd0;\n"
        "            tx_out <= 1'b0;\n"
        "        end\n"
        "    end\n"
        "endmodule\n")
    found = multi_driver_regs(rtl)
    assert any("baud_cnt" in f for f in found), found


def test_single_owner_rtl_is_clean(tmp_path) -> None:
    from verilog_check import multi_driver_regs

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "uart_tx.v").write_text(
        "module uart_tx(input clk, input tx_start, output reg tx_out);\n"
        "    reg [31:0] baud_cnt;\n"
        "    always @(posedge clk) begin\n"
        "        if (baud_cnt == 433) baud_cnt <= 32'd0;\n"
        "        else baud_cnt <= baud_cnt + 32'd1;\n"
        "    end\n"
        "    always @(posedge clk) begin\n"
        "        if (tx_start) tx_out <= 1'b0;\n"
        "    end\n"
        "endmodule\n")
    assert multi_driver_regs(rtl) == []


def test_the_same_name_in_two_modules_is_not_a_conflict(tmp_path) -> None:
    from verilog_check import multi_driver_regs

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "two.v").write_text(
        "module a(input clk);\n  reg [3:0] cnt;\n"
        "  always @(posedge clk) begin cnt <= cnt + 1; end\nendmodule\n"
        "module b(input clk);\n  reg [3:0] cnt;\n"
        "  always @(posedge clk) begin cnt <= cnt - 1; end\nendmodule\n")
    assert multi_driver_regs(rtl) == []
