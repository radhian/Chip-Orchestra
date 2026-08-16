"""HW/SW co-verification: interface detection, bench derivation, block diagrams.

These cover the parts that decide whether the stage talks to the chip CORRECTLY
— what the top-level ports mean, and whether the derived interface bench really
reads the host driver's stimulus instead of the canonical image baked into the
RTL. A silent mistake in either turns the gate into a picture of the wrong run.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents import hwsw
from reporting import diagrams

PARAMS_VH = """\
`ifndef PARAMS_VH
`define PARAMS_VH
`define CLK_FREQ   32'd50_000_000
`define BAUD_RATE  32'd115_200
`define BAUD_DIV   32'd434
`define DATA_W     8
`define IMG_W      32
`define IMG_H      32
`define OUT_W      30
`define OUT_H      30
`endif
"""

TOP_V = """\
`include "params.vh"
module chip_top (
    input  wire clk,
    input  wire rst_async_n,
    input  wire data_i,
    output wire data_o
);
    wire [`DATA_W-1:0] byte_out;
    wire valid;
    rx_unit u_rx (.clk(clk), .rst_n(rst_async_n), .rx_in(data_i),
                  .rx_byte(byte_out), .rx_valid(valid));
    tx_unit u_tx (.clk(clk), .rst_n(rst_async_n), .data_in(byte_out),
                  .send(valid), .tx_out(data_o));
endmodule
"""

RX_V = """\
`include "params.vh"
module rx_unit (
    input  wire clk,
    input  wire rst_n,
    input  wire rx_in,
    output reg  [`DATA_W-1:0] rx_byte,
    output reg  rx_valid
);
endmodule
"""

TX_V = """\
module tx_unit (
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] data_in,
    input  wire send,
    output reg  tx_out
);
endmodule
"""

TOP_TB_V = """\
`timescale 1ns/1ps
module chip_top_tb;
    reg clk, rst_async_n, data_i;
    wire data_o;
    reg [7:0] img [0:1023];
    reg [7:0] golden [0:899];
    reg [7:0] out [0:899];
    chip_top dut (.clk(clk), .rst_async_n(rst_async_n),
                  .data_i(data_i), .data_o(data_o));
    initial begin
        $readmemh("rtl/chip_input.mem", img);
        $readmemh("waves/golden_output.mem", golden);
        $dumpfile("design.vcd");
        $dumpvars(0, chip_top_tb);
        $writememh("waves/chip_output.mem", out);
        $display("written to waves/chip_output.mem");
        $finish;
    end
endmodule
"""


def _design(tmp_path: Path) -> Path:
    (tmp_path / "rtl").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tb").mkdir(parents=True, exist_ok=True)
    (tmp_path / "rtl" / "params.vh").write_text(PARAMS_VH)
    (tmp_path / "rtl" / "chip_top.v").write_text(TOP_V)
    (tmp_path / "rtl" / "rx_unit.v").write_text(RX_V)
    (tmp_path / "rtl" / "tx_unit.v").write_text(TX_V)
    (tmp_path / "tb" / "chip_top_tb.v").write_text(TOP_TB_V)
    return tmp_path


def test_top_ports_do_not_leak_into_each_other(tmp_path: Path) -> None:
    """A comma-separated port list must not run past its own declaration.

    Matching a name list directly swallowed the newline and reported a port
    literally called "input", which made the interface look parallel."""
    ports = hwsw.top_ports(_design(tmp_path), "chip_top")
    assert [p["name"] for p in ports] == ["clk", "rst_async_n", "data_i", "data_o"]
    assert all(p["width"] == 1 for p in ports)


def test_detect_interface_reads_a_serial_chip(tmp_path: Path) -> None:
    iface = hwsw.detect_interface(_design(tmp_path), "chip_top")
    assert iface["kind"] == "serial"
    assert iface["clock"] == "clk"
    assert iface["reset"] == "rst_async_n" and iface["reset_active_low"]
    assert iface["data_in"] == ["data_i"] and iface["data_out"] == ["data_o"]
    assert iface["baud_div"] == 434          # from `define, not recomputed
    assert (iface["img_w"], iface["out_w"]) == (32, 30)


def test_widths_resolve_through_macros(tmp_path: Path) -> None:
    ports = hwsw.top_ports(_design(tmp_path), "rx_unit")
    widths = {p["name"]: p["width"] for p in ports}
    assert widths["rx_byte"] == 8            # [`DATA_W-1:0]
    assert widths["rx_valid"] == 1


def test_derived_bench_reads_the_driver_stimulus(tmp_path: Path) -> None:
    """The derived bench must talk to the HW/SW files, not the canonical ones.

    If it kept reading rtl/chip_input.mem the gate would show the result of the
    image baked into the design while claiming it was the user's upload."""
    workspace = _design(tmp_path)
    iface = hwsw.detect_interface(workspace, "chip_top")
    source, provenance = hwsw.derive_testbench(workspace, "chip_top", iface)

    assert "chip_top_tb.v" in provenance
    assert f'$readmemh("{hwsw.STIMULUS_REL}"' in source
    assert f'$readmemh("{hwsw.EXPECTED_MEM_REL}"' in source
    assert f'$writememh("{hwsw.CHIP_MEM_REL}"' in source
    assert "rtl/chip_input.mem" not in source
    assert "waves/golden_output.mem" not in source
    assert "waves/chip_output.mem" not in source
    assert "module chip_top_hwsw_tb;" in source
    # The DUT itself is untouched — this stage verifies the chip, it does not
    # get to change it.
    assert "chip_top dut" in source


def test_derived_bench_dumps_only_the_interface_nets(tmp_path: Path) -> None:
    """Level-0 dumps of this design run to hundreds of megabytes, and the clock
    accounts for nearly all of it."""
    workspace = _design(tmp_path)
    iface = hwsw.detect_interface(workspace, "chip_top")
    source, _ = hwsw.derive_testbench(workspace, "chip_top", iface)

    assert f'$dumpfile("{hwsw.VCD_REL}")' in source
    assert "$dumpvars(0, rst_async_n, data_i, data_o)" in source
    assert "$dumpvars(0, chip_top_tb)" not in source


def test_active_input_marker_wins_over_mtime(tmp_path: Path) -> None:
    workspace = _design(tmp_path)
    (workspace / "hwsw" / "input").mkdir(parents=True, exist_ok=True)
    chosen = workspace / "hwsw" / "input" / "old.png"
    chosen.write_bytes(b"x")
    newer = workspace / "hwsw" / "input" / "new.png"
    newer.write_bytes(b"y")
    (workspace / hwsw.ACTIVE_INPUT_REL).write_text("hwsw/input/old.png\n")

    assert hwsw.resolve_input(workspace) == chosen


def test_resolve_input_falls_back_to_the_canonical_stimulus(tmp_path: Path) -> None:
    """The gate must be able to show a result before anything is uploaded."""
    workspace = _design(tmp_path)
    (workspace / "rtl" / "chip_input.mem").write_text("00\n01\n")
    assert hwsw.resolve_input(workspace) == workspace / "rtl" / "chip_input.mem"


def test_block_diagram_covers_every_instance_and_omits_clock_nets(tmp_path: Path) -> None:
    workspace = _design(tmp_path)
    design = diagrams.parse_design(workspace / "rtl")
    assert set(design["modules"]) == {"chip_top", "rx_unit", "tx_unit"}
    assert [e["inst"] for e in design["insts"]["chip_top"]] == ["u_rx", "u_tx"]

    tikz = diagrams.top_level_diagram(design, "chip_top")
    assert "(inst_u_rx)" in tikz and "(inst_u_tx)" in tikz
    assert "byte" in tikz and "out" in tikz   # the data net between the blocks
    assert "pad_clk" not in tikz              # clock and reset are not drawn
    assert "pad_rst_async_n" not in tikz
    # data pins ARE drawn
    assert "(pad_data_i)" in tikz and "(pad_data_o)" in tikz


def test_ip_symbol_labels_every_port_with_its_width(tmp_path: Path) -> None:
    workspace = _design(tmp_path)
    design = diagrams.parse_design(workspace / "rtl")
    tikz = diagrams.ip_symbol("rx_unit", design["modules"]["rx_unit"]["ports"])
    plain = tikz.replace("\\allowbreak{}", "").replace("\\_", "_")
    assert "rx_byte" in plain and "[7:0]" in plain
    assert "rx_valid" in plain and "rx_in" in plain
    assert "\\begin{tikzpicture}" in tikz and "\\end{tikzpicture}" in tikz
