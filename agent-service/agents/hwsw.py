"""Hardware/software co-verification — the HW_SW_VERIFY stage's engine.

SIM proves the RTL reproduces the golden model on the CANONICAL input that was
baked into the design. That is a necessary check and not a sufficient one: it
says nothing about whether the chip can be *used*. A real user hands the device
a file over a wire, and something on the host side has to encode it into the
exact frames the top-level RTL speaks and decode whatever comes back.

This module builds and runs that bridge:

* :func:`detect_interface` reads the TOP MODULE'S PORTS (plus the design's
  parameter header) and works out how the chip is talked to — a bit-serial UART
  pair, a parallel bus with a handshake, …  — together with the timing
  constants (baud divisor, clock period) and data geometry that govern it.
* :func:`derive_testbench` writes the **hardware side**: a Verilog interface
  bench that instantiates the DUT and replays a byte stream over that physical
  interface. It is derived from the top-level testbench that already passed SIM
  whenever one exists — that file is proof of how the protocol actually works,
  so re-deriving the protocol from scratch would only invent a second opinion.
* :func:`fallback_driver_source` writes the **software side**: a Python host
  driver that converts a user-supplied file into the chip's byte stream, runs
  the golden model on the SAME input to get the expected answer, and decodes the
  chip's response back into a picture.
* :func:`run_cosim` compiles and runs the pair, and :func:`render_waveform`
  turns the interface VCD into something a reviewer can look at.

Everything here is deterministic. The stage handler calls a deep agent only to
REPAIR what this module could not derive — the framework owns the plumbing, the
agent owns design content, which is the same split the rest of the flow uses.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Workspace-relative contract. Every one of these paths is also written into the
# deep-agent prompt, so the agent and the framework cannot drift apart.
DRIVER_REL = "sw/hwsw/host_driver.py"
STIMULUS_REL = "hwsw/stimulus.mem"
EXPECTED_MEM_REL = "hwsw/expected_output.mem"
CHIP_MEM_REL = "hwsw/chip_output.mem"
ENCODE_REL = "hwsw/encode.json"
VERIFY_REL = "hwsw/verify.json"
VCD_REL = "hwsw/hwsw.vcd"
LOG_REL = "logs/hw_sw_verify.log"
REPORT_REL = "reports/hw_sw_verify_report.json"
ACTIVE_INPUT_REL = "hwsw/active_input.txt"

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}

_TYPE_KW = {"wire", "reg", "logic", "signed", "unsigned", "var", "bit", "integer", "real"}

_CLOCK_RE = re.compile(r"^(i_)?(clk|clock)(_i|_in)?\d*$", re.I)
_RESET_RE = re.compile(r"(rst|reset)", re.I)
_SERIAL_HINT_RE = re.compile(r"(uart|rx|tx|serial|sin|sout|sda|scl|miso|mosi|sclk|data_[io]$)", re.I)


# --------------------------------------------------------------------------- #
# Top-level interface detection
# --------------------------------------------------------------------------- #
def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def _module_text(rtl_dir: Path, module: str) -> str:
    """The source of one module, header through ``endmodule`` ('' when absent)."""
    for path in sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv")):
        try:
            clean = _strip_comments(path.read_text(errors="replace"))
        except OSError:
            continue
        match = re.search(r"\bmodule\s+" + re.escape(module) + r"\b", clean)
        if not match:
            continue
        end = clean.find("endmodule", match.end())
        return clean[match.start(): end if end != -1 else len(clean)]
    return ""


def design_constants(workspace: Path) -> Dict[str, int]:
    """Integer design constants, from the RTL header first and the golden
    model's mirror of it second (`define CLK_FREQ 32'd50_000_000 → 50000000).

    The RTL header wins: it is what the silicon was built from, and a golden
    params.py that drifted from it would silently mis-time the host driver."""
    out: Dict[str, int] = {}

    def _num(token: str) -> Optional[int]:
        token = token.strip().rstrip(";").strip()
        token = re.sub(r"_", "", token)
        # Verilog sized literals: 32'd50000000, 8'hA0, 4'b1010
        sized = re.match(r"^\d*'([dhbo])([0-9a-fA-F]+)$", token)
        if sized:
            base = {"d": 10, "h": 16, "b": 2, "o": 8}[sized.group(1).lower()]
            try:
                return int(sized.group(2), base)
            except ValueError:
                return None
        try:
            return int(token, 0)
        except ValueError:
            return None

    for header in sorted((workspace / "rtl").glob("*.vh")) + sorted((workspace / "rtl").glob("*.v")):
        try:
            body = _strip_comments(header.read_text(errors="replace"))
        except OSError:
            continue
        for name, value in re.findall(r"`define\s+([A-Za-z_]\w*)\s+([^\n]+)", body):
            if name not in out:
                parsed = _num(value)
                if parsed is not None:
                    out[name] = parsed
        for name, value in re.findall(r"\bparameter\s+(?:integer\s+)?([A-Za-z_]\w*)\s*=\s*([^,;)\n]+)", body):
            if name not in out:
                parsed = _num(value)
                if parsed is not None:
                    out[name] = parsed

    params_py = workspace / "golden" / "model" / "params.py"
    if params_py.is_file():
        try:
            body = params_py.read_text(errors="replace")
        except OSError:
            body = ""
        for name, value in re.findall(r"^([A-Z][A-Z0-9_]*)\s*=\s*([0-9_]+)", body, re.M):
            out.setdefault(name, int(value.replace("_", "")))

    marker = workspace / "context" / "input_size.txt"
    if marker.is_file():
        try:
            side = int(marker.read_text().strip())
            if side > 0:
                out.setdefault("IMG_W", side)
                out.setdefault("IMG_H", side)
        except (OSError, ValueError):
            pass
    return out


def _resolve_width(expr: str, consts: Dict[str, int]) -> int:
    """Width of a `[msb:lsb]` range, resolving `MACRO / PARAM names (1 when the
    port is a bare scalar, 0 when the expression cannot be evaluated)."""
    expr = expr.strip()
    if not expr:
        return 1
    body = expr.strip("[]")
    if ":" not in body:
        return 1
    msb, lsb = body.split(":", 1)

    def _eval(part: str) -> Optional[int]:
        part = part.replace("`", "")
        for name, value in consts.items():
            part = re.sub(r"\b" + re.escape(name) + r"\b", str(value), part)
        if not re.fullmatch(r"[0-9+\-*/() ]+", part.strip() or "x"):
            return None
        try:
            return int(eval(part, {"__builtins__": {}}, {}))  # noqa: S307 - digits/operators only
        except Exception:  # noqa: BLE001
            return None

    hi, lo = _eval(msb), _eval(lsb)
    if hi is None or lo is None:
        return 0
    return abs(hi - lo) + 1


def top_ports(workspace: Path, top: str, consts: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
    """``[{name, dir, width}]`` for the top module, in declaration order.

    Handles both ANSI headers (``module m (input wire clk, ...)``) and the
    non-ANSI form where directions are declared in the body."""
    consts = consts if consts is not None else design_constants(workspace)
    text = _module_text(workspace / "rtl", top)
    if not text:
        return []
    ports: List[Dict[str, Any]] = []
    seen = set()
    # One declaration runs from a direction keyword to the next direction
    # keyword, a ';' or the close of the port list. Matching a comma-separated
    # NAME LIST directly does not work: the list happily runs past the newline
    # into the next declaration, so `input wire clk,\n input wire data_i` came
    # back as a port literally named "input".
    for match in re.finditer(
        r"\b(input|output|inout)\b((?:(?!\b(?:input|output|inout)\b)[^;)])*)", text
    ):
        direction, decl = match.group(1), match.group(2)
        width_match = re.search(r"\[[^\]]*\]", decl)
        width_expr = width_match.group(0) if width_match else ""
        width = _resolve_width(width_expr, consts)
        for name in re.findall(r"\b([A-Za-z_]\w*)\b", re.sub(r"\[[^\]]*\]", " ", decl)):
            if name in _TYPE_KW or name in seen:
                continue
            seen.add(name)
            ports.append({"name": name, "dir": direction, "width": width,
                          "width_expr": width_expr.strip()})
    return ports


def detect_interface(workspace: Path, top: str) -> Dict[str, Any]:
    """How software talks to this chip.

    Returns the port classification, the interface KIND (``serial`` when the
    payload crosses on a single wire in each direction, ``parallel`` when it
    crosses on a bus), and the timing/geometry constants the host driver needs.
    """
    consts = design_constants(workspace)
    ports = top_ports(workspace, top, consts)

    clocks = [p for p in ports if _CLOCK_RE.match(p["name"])]
    resets = [p for p in ports if p not in clocks and _RESET_RE.search(p["name"])
              and p["dir"] == "input" and p["width"] == 1]
    control = {p["name"] for p in clocks} | {p["name"] for p in resets}
    data_in = [p for p in ports if p["dir"] == "input" and p["name"] not in control]
    data_out = [p for p in ports if p["dir"] == "output" and p["name"] not in control]

    payload_in = [p for p in data_in if p["width"] != 1] or data_in
    payload_out = [p for p in data_out if p["width"] != 1] or data_out
    serial = (len(data_in) == 1 and len(data_out) >= 1
              and data_in[0]["width"] == 1
              and all(p["width"] == 1 for p in data_out))
    if not serial and data_in and data_out:
        serial = (all(p["width"] == 1 for p in data_in + data_out)
                  and any(_SERIAL_HINT_RE.search(p["name"]) for p in data_in + data_out))

    baud_div = 0
    for key in ("BAUD_DIV", "BIT_TICKS", "CLKS_PER_BIT", "DIVISOR", "BAUD_TICKS"):
        if consts.get(key):
            baud_div = int(consts[key])
            break
    if not baud_div and consts.get("CLK_FREQ") and consts.get("BAUD_RATE"):
        baud_div = max(1, int(consts["CLK_FREQ"]) // int(consts["BAUD_RATE"]))

    img_w = int(consts.get("IMG_W") or consts.get("IN_W") or 0)
    img_h = int(consts.get("IMG_H") or consts.get("IN_H") or img_w)
    out_w = int(consts.get("OUT_W") or 0)
    out_h = int(consts.get("OUT_H") or out_w)

    return {
        "top": top,
        "kind": "serial" if serial else ("parallel" if payload_in else "unknown"),
        "clock": clocks[0]["name"] if clocks else "clk",
        "reset": resets[0]["name"] if resets else "",
        "reset_active_low": bool(resets and re.search(r"(_n$|n$|nrst)", resets[0]["name"], re.I)),
        "data_in": [p["name"] for p in data_in],
        "data_out": [p["name"] for p in data_out],
        "payload_in_width": payload_in[0]["width"] if payload_in else 0,
        "payload_out_width": payload_out[0]["width"] if payload_out else 0,
        "ports": ports,
        "baud_div": baud_div,
        "data_width": int(consts.get("DATA_W") or 8),
        "img_w": img_w, "img_h": img_h, "out_w": out_w, "out_h": out_h,
        "constants": {k: v for k, v in consts.items()
                      if k in ("CLK_FREQ", "BAUD_RATE", "BAUD_DIV", "DATA_W",
                               "IMG_W", "IMG_H", "OUT_W", "OUT_H")},
    }


def describe_interface(iface: Dict[str, Any]) -> str:
    """One paragraph a human (and the repair agent) can read."""
    ports = ", ".join(f"{p['dir']} {'[%d bits] ' % p['width'] if p['width'] != 1 else ''}{p['name']}"
                      for p in iface.get("ports", []))
    lines = [f"Top module `{iface.get('top')}` ports: {ports or 'n/a'}."]
    if iface.get("kind") == "serial":
        lines.append(
            f"Interface is BIT-SERIAL (UART-style): payload enters on `{', '.join(iface['data_in'])}` "
            f"and leaves on `{', '.join(iface['data_out'])}`, one bit per baud period of "
            f"{iface.get('baud_div') or '?'} clock cycles, {iface.get('data_width', 8)} data bits "
            "per frame, LSB first, with a low start bit and a high stop bit.")
    elif iface.get("kind") == "parallel":
        lines.append(
            f"Interface is PARALLEL: payload enters on `{', '.join(iface['data_in'])}` "
            f"({iface.get('payload_in_width')} bits) and leaves on "
            f"`{', '.join(iface['data_out'])}` ({iface.get('payload_out_width')} bits).")
    if iface.get("img_w"):
        lines.append(f"Data geometry: input {iface['img_w']}x{iface['img_h']}"
                     + (f", output {iface['out_w']}x{iface['out_h']}" if iface.get("out_w") else "")
                     + " bytes.")
    return " ".join(lines)


# --------------------------------------------------------------------------- #
# Choosing the input the chip should process
# --------------------------------------------------------------------------- #
def resolve_input(workspace: Path) -> Optional[Path]:
    """The file the chip is asked to process, in priority order: the one the
    reviewer just uploaded through the gate, then the newest file they uploaded
    before, then the picture attached to the task, then the canonical stimulus
    baked into the RTL. The stage must always have SOMETHING to run so the gate
    can present a result before the user has uploaded anything."""
    marker = workspace / ACTIVE_INPUT_REL
    if marker.is_file():
        try:
            rel = marker.read_text(errors="replace").strip().splitlines()[0].strip()
        except (OSError, IndexError):
            rel = ""
        if rel and not rel.startswith("/") and ".." not in rel:
            candidate = workspace / rel
            if candidate.is_file():
                return candidate

    def newest(directory: Path, exts: Optional[set] = None) -> Optional[Path]:
        if not directory.is_dir():
            return None
        files = [p for p in directory.iterdir()
                 if p.is_file() and not p.name.startswith(".")
                 and (exts is None or p.suffix.lower() in exts)]
        return max(files, key=lambda p: p.stat().st_mtime) if files else None

    def attached_data_image() -> Optional[Path]:
        """The attachment the vision triage classified as CHIP INPUT DATA.

        A task typically comes with two pictures — an architecture diagram and
        the picture the accelerator is supposed to process. Taking whichever
        was written last would sometimes feed the chip a block diagram."""
        try:
            from uploads import uploads_manifest
            manifest = uploads_manifest(workspace) or {}
        except Exception:  # noqa: BLE001
            return None
        for name, role in manifest.items():
            candidate = workspace / "context" / "uploads" / name
            if role == "data" and candidate.is_file():
                return candidate
        return None

    for candidate in (newest(workspace / "hwsw" / "input"),
                      attached_data_image(),
                      newest(workspace / "context" / "uploads", _IMAGE_EXT)):
        if candidate is not None:
            return candidate
    rtl = workspace / "rtl"
    if rtl.is_dir():
        for mem in sorted(rtl.glob("*input*.mem")):
            return mem
    return None


# --------------------------------------------------------------------------- #
# Hardware side: the Verilog interface bench
# --------------------------------------------------------------------------- #
def _sim_tb_path(workspace: Path, top: str) -> Optional[Path]:
    """The top-level testbench SIM already validated — the authority on how this
    chip's physical protocol behaves."""
    tb = workspace / "tb"
    if not tb.is_dir():
        return None
    for name in (f"{top}_tb.v", f"tb_{top}.v", f"{top}_top_tb.v"):
        if (tb / name).is_file():
            return tb / name
    # Fall back to the largest bench that names the top module — unit benches
    # instantiate their own IP and never mention it.
    candidates = [p for p in tb.glob("*_tb.v") if top in p.read_text(errors="replace")]
    return max(candidates, key=lambda p: p.stat().st_size) if candidates else None


def _dut_nets(tb_text: str, top: str, iface: Dict[str, Any]) -> List[str]:
    """The bench-side nets wired to the DUT's ports, excluding the clock.

    Read from the instantiation itself (``.data_i(data_i)``) rather than assumed
    from the port names — a bench is free to call its nets whatever it likes,
    and dumping a name that does not exist is a compile error."""
    match = re.search(re.escape(top) + r"\s+\w+\s*\((.*?)\)\s*;", tb_text, re.S)
    if not match:
        return []
    clock = (iface.get("clock") or "clk").lower()
    nets: List[str] = []
    for port, net in re.findall(r"\.\s*(\w+)\s*\(\s*([A-Za-z_]\w*)\s*\)", match.group(1)):
        if port.lower() == clock or net.lower() == clock or net in nets:
            continue
        nets.append(net)
    return nets


def derive_testbench(workspace: Path, top: str, iface: Dict[str, Any]) -> Tuple[str, str]:
    """Build the interface bench from the validated top-level testbench.

    Returns ``(source, provenance)``. The transformation is deliberately small:
    the protocol timing, the fork/join sender-receiver structure and the frame
    format are all already correct in the SIM bench, so only the FILES it talks
    to change — stimulus comes from the host driver instead of the RTL's baked
    canonical image, the expected values come from the driver's run of the
    golden model on that same input, and the dumps land under ``hwsw/``.
    Re-deriving the protocol instead would be inventing a second opinion about
    a question the passing SIM already answered.
    """
    source_tb = _sim_tb_path(workspace, top)
    if source_tb is None:
        return "", "none"
    try:
        text = source_tb.read_text(errors="replace")
    except OSError:
        return "", "none"

    module_match = re.search(r"\bmodule\s+([A-Za-z_]\w*)", text)
    if not module_match:
        return "", "none"
    old_module = module_match.group(1)
    new_module = f"{top}_hwsw_tb"

    # $readmemh of the canonical stimulus -> the host driver's encoded stream.
    def _redirect_read(match: re.Match) -> str:
        path = match.group(1)
        low = path.lower()
        if "golden" in low or "expect" in low:
            return match.group(0).replace(path, EXPECTED_MEM_REL)
        if low.endswith(".mem"):
            return match.group(0).replace(path, STIMULUS_REL)
        return match.group(0)

    text = re.sub(r"\$readmemh\s*\(\s*\"([^\"]+)\"", _redirect_read, text)
    text = re.sub(r"(\$writememh\s*\(\s*\")[^\"]*chip[^\"]*(\")",
                  r"\g<1>" + CHIP_MEM_REL + r"\g<2>", text)
    text = re.sub(r"(\$dumpfile\s*\(\s*\")[^\"]*(\")", r"\g<1>" + VCD_REL + r"\g<2>", text)
    # Dump the INTERFACE NETS ONLY — the wires the DUT is actually connected to,
    # minus the clock. A full-hierarchy dump of this design was 256 MB in SIM,
    # and even the bench's own scope came out at 140 MB because a 44 ms run
    # toggles the clock nine million times. What this gate is about is the
    # handful of transitions on the data lines, and a waveform nobody can open
    # is not evidence.
    interface_nets = _dut_nets(text, top, iface)
    if interface_nets:
        dump = "$dumpvars(0, " + ", ".join(interface_nets) + ")"
    else:
        dump = f"$dumpvars(1, {new_module})"
    text = re.sub(r"\$dumpvars\s*\([^;]*\)", dump, text, count=1)
    text = re.sub(r"\b" + re.escape(old_module) + r"\b", new_module, text)
    # Console strings still naming the SIM paths would tell the reviewer the
    # result went somewhere it did not.
    text = text.replace("waves/chip_output.mem", CHIP_MEM_REL)
    text = text.replace("waves/golden_output.mem", EXPECTED_MEM_REL)

    header = (
        f"// {new_module} — HW/SW co-verification interface bench (generated).\n"
        f"// Derived from tb/{source_tb.name}, the top-level testbench that passed SIM,\n"
        "// so the physical protocol (frame format, baud timing, sender/receiver\n"
        "// structure) is the one the chip is already known to speak.\n"
        "//\n"
        "// What changed: the stimulus is whatever the Python host driver encoded from\n"
        f"// the user's input ({STIMULUS_REL}), the expected values are the golden\n"
        f"// model's answer for THAT SAME input ({EXPECTED_MEM_REL}), and the chip's\n"
        f"// response is dumped to {CHIP_MEM_REL} for the driver to decode.\n"
    )
    if not text.lstrip().startswith("//"):
        text = header + text
    else:
        text = header + "\n" + text
    return text, f"derived from tb/{source_tb.name}"


def fallback_tb_source(top: str, iface: Dict[str, Any], n_in: int, n_out: int) -> str:
    """A UART interface bench written from the detected ports alone.

    Used only when the design has no top-level testbench to derive from. Handles
    the bit-serial case, which is what a chip with a one-wire-each-way interface
    always is; a parallel design without a reference bench is handed to the
    repair agent instead."""
    data_i = iface["data_in"][0] if iface.get("data_in") else "data_i"
    data_o = iface["data_out"][0] if iface.get("data_out") else "data_o"
    clk = iface.get("clock") or "clk"
    rst = iface.get("reset") or "rst_n"
    active_low = iface.get("reset_active_low", True)
    baud = iface.get("baud_div") or 434
    bits = iface.get("data_width") or 8
    assert_rst, deassert_rst = ("0", "1") if active_low else ("1", "0")
    return f"""// {top}_hwsw_tb — HW/SW co-verification interface bench (generated).
// No top-level testbench was available to derive from, so this bench is written
// from the TOP MODULE'S PORTS: a {bits}-bit UART frame (low start bit, LSB
// first, high stop bit) at {baud} clock cycles per bit.
`timescale 1ns/1ps

module {top}_hwsw_tb;
    localparam integer BAUD_DIV  = {baud};
    localparam integer HALF_BAUD = BAUD_DIV / 2;
    localparam integer N_IN      = {n_in};
    localparam integer N_OUT     = {n_out};

    reg  {clk};
    reg  {rst};
    reg  {data_i};
    wire {data_o};

    reg [{bits - 1}:0] stimulus [0:N_IN-1];
    reg [{bits - 1}:0] captured [0:N_OUT-1];
    integer n_captured;
    integer i;

    {top} dut (.{clk}({clk}), .{rst}({rst}), .{data_i}({data_i}), .{data_o}({data_o}));

    initial {clk} = 1'b0;
    always #5 {clk} = ~{clk};

    task send_byte(input [{bits - 1}:0] value);
        integer b;
        begin
            {data_i} = 1'b0;
            repeat (BAUD_DIV) @(posedge {clk});
            for (b = 0; b < {bits}; b = b + 1) begin
                {data_i} = value[b];
                repeat (BAUD_DIV) @(posedge {clk});
            end
            {data_i} = 1'b1;
            repeat (BAUD_DIV) @(posedge {clk});
        end
    endtask

    task recv_byte(output [{bits - 1}:0] value);
        integer b;
        begin
            value = 0;
            while ({data_o} === 1'b1) @(posedge {clk});
            repeat (HALF_BAUD + BAUD_DIV) @(posedge {clk});
            for (b = 0; b < {bits}; b = b + 1) begin
                value[b] = {data_o};
                repeat (BAUD_DIV) @(posedge {clk});
            end
        end
    endtask

    reg [{bits - 1}:0] rx_value;

    initial begin
        $readmemh("{STIMULUS_REL}", stimulus);
        $dumpfile("{VCD_REL}");
        $dumpvars(0, {rst}, {data_i}, {data_o});
        {rst} = 1'b{assert_rst};
        {data_i} = 1'b1;
        n_captured = 0;
        repeat (10) @(posedge {clk});
        {rst} = 1'b{deassert_rst};
        repeat (5) @(posedge {clk});
        $display("HWSW: sending %0d bytes, expecting %0d back", N_IN, N_OUT);
        fork
            begin
                for (i = 0; i < N_IN; i = i + 1) send_byte(stimulus[i]);
            end
            begin
                while (n_captured < N_OUT) begin
                    recv_byte(rx_value);
                    captured[n_captured] = rx_value;
                    n_captured = n_captured + 1;
                end
            end
        join
        $writememh("{CHIP_MEM_REL}", captured);
        $display("HWSW: captured %0d bytes -> {CHIP_MEM_REL}", n_captured);
        $finish;
    end

    initial begin
        repeat (100000000) @(posedge {clk});
        $display("HWSW TIMEOUT: the chip did not return %0d bytes", N_OUT);
        $finish;
    end
endmodule
"""


# --------------------------------------------------------------------------- #
# Software side: the Python host driver
# --------------------------------------------------------------------------- #
def fallback_driver_source(iface: Dict[str, Any]) -> str:
    """A host driver written from the detected interface.

    It is the software a user would actually write to drive this chip: open the
    file, convert it to the chip's sample format and geometry, hand the bytes to
    the link, then reassemble what comes back. The link itself is the Verilog
    interface bench rather than a serial port, which is the only difference
    between this and a program talking to the fabricated device.
    """
    img_w = iface.get("img_w") or 0
    img_h = iface.get("img_h") or img_w
    out_w = iface.get("out_w") or 0
    out_h = iface.get("out_h") or out_w
    return f'''#!/usr/bin/env python3
"""host_driver.py — the SOFTWARE side of the chip's interface (generated).

This is the program a host would run to use the accelerator. It knows three
things about the hardware, all read off the top-level RTL:

  * the sample format   : {iface.get("data_width", 8)}-bit values
  * the input geometry  : {img_w}x{img_h}
  * the output geometry : {out_w}x{out_h}

`encode` turns a user file (an image, or a raw/hex byte dump) into the exact
byte stream the chip expects and ALSO computes what the Python golden model
says the answer should be, so the run is checkable. `decode` turns the bytes
the chip sent back into a picture and compares them value-for-value.

Run from the workspace root:
    python3 {DRIVER_REL} encode --input <file>
    python3 {DRIVER_REL} decode
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

IMG_W, IMG_H = {img_w or 0}, {img_h or 0}
OUT_W, OUT_H = {out_w or 0}, {out_h or 0}
SAMPLE_MAX = {(1 << int(iface.get("data_width", 8) or 8)) - 1}

ROOT = Path(__file__).resolve().parents[2]
STIMULUS = ROOT / "{STIMULUS_REL}"
EXPECTED = ROOT / "{EXPECTED_MEM_REL}"
CHIP = ROOT / "{CHIP_MEM_REL}"
ENCODE_JSON = ROOT / "{ENCODE_REL}"
VERIFY_JSON = ROOT / "{VERIFY_REL}"


# ----------------------------------------------------------------- utilities
def _read_mem(path: Path):
    """Hex tokens of a .mem file (skipping comments and @address directives)."""
    values = []
    try:
        body = path.read_text(errors="replace")
    except OSError:
        return values
    for line in body.splitlines():
        line = line.split("//")[0]
        for token in line.split():
            if token.startswith("@"):
                continue
            try:
                values.append(int(token, 16))
            except ValueError:
                pass
    return values


def _write_mem(path: Path, values) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\\n".join(f"{{v & SAMPLE_MAX:02x}}" for v in values) + "\\n")


def _save_png(values, width: int, height: int, path: Path) -> bool:
    """Render a flat sample list as a grayscale picture, upscaled so a 30x30
    result is actually visible in a browser."""
    try:
        from PIL import Image
    except Exception:
        return False
    if width <= 0 or height <= 0:
        return False
    padded = list(values[: width * height]) + [0] * max(0, width * height - len(values))
    image = Image.new("L", (width, height))
    image.putdata([max(0, min(255, int(v))) for v in padded])
    scale = max(1, 320 // max(width, height))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.resize((width * scale, height * scale), Image.NEAREST).save(path)
    return True


def _load_samples(source: Path):
    """A user file -> the flat sample list the chip consumes."""
    suffix = source.suffix.lower()
    if suffix in {{".mem", ".hex"}}:
        return _read_mem(source)
    if suffix in {{".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}}:
        from PIL import Image
        image = Image.open(source).convert("L")
        if IMG_W and IMG_H:
            image = image.resize((IMG_W, IMG_H), Image.LANCZOS)
        return list(image.getdata())
    if suffix in {{".txt", ".csv"}}:
        text = source.read_text(errors="replace").replace(",", " ")
        return [int(float(tok)) for tok in text.split() if tok.strip("+-.").replace(".", "").isdigit()]
    return list(source.read_bytes())


# ------------------------------------------------------------- golden model
def _golden(samples):
    """Run the approved Python reference on the same input, if it exposes a
    whole-frame entry point. Returns (values, note) — an empty list simply means
    the run is unchecked and the reviewer's eyes are the verdict."""
    sys.path.insert(0, str(ROOT / "golden"))
    sys.path.insert(0, str(ROOT))
    try:
        from model import top as golden_top
    except Exception as exc:
        return [], f"golden model not importable ({{exc}})"
    expected_len = OUT_W * OUT_H if OUT_W and OUT_H else 0
    names = [n for n in dir(golden_top) if not n.startswith("_") and callable(getattr(golden_top, n))]
    names.sort(key=lambda n: 0 if any(k in n.lower() for k in
               ("stream", "process", "run", "top", "compute", "forward", "apply")) else 1)
    for name in names:
        try:
            result = getattr(golden_top, name)(list(samples))
        except Exception:
            continue
        try:
            values = [int(v) for v in result]
        except Exception:
            continue
        if values and (not expected_len or len(values) == expected_len):
            return values, f"golden/model/top.py::{{name}}"
    return [], "no whole-frame entry point found in golden/model/top.py"


# ----------------------------------------------------------------- commands
def cmd_encode(args) -> int:
    source = Path(args.input)
    if not source.is_absolute():
        source = ROOT / source
    samples = _load_samples(source)
    if IMG_W and IMG_H:
        need = IMG_W * IMG_H
        samples = (list(samples) + [0] * need)[:need]
    _write_mem(STIMULUS, samples)
    _save_png(samples, IMG_W, IMG_H, ROOT / "hwsw" / "input_preview.png")

    expected, note = _golden(samples)
    if expected:
        _write_mem(EXPECTED, expected)
        _save_png(expected, OUT_W or IMG_W, OUT_H or IMG_H, ROOT / "hwsw" / "expected_output.png")

    payload = {{
        "input": str(source.relative_to(ROOT)) if str(source).startswith(str(ROOT)) else str(source),
        "bytes_in": len(samples),
        "bytes_out": len(expected) if expected else (OUT_W * OUT_H if OUT_W and OUT_H else 0),
        "in_geometry": [IMG_W, IMG_H],
        "out_geometry": [OUT_W, OUT_H],
        "golden": note,
        "golden_available": bool(expected),
    }}
    ENCODE_JSON.parent.mkdir(parents=True, exist_ok=True)
    ENCODE_JSON.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


def cmd_decode(args) -> int:
    chip = _read_mem(CHIP)
    expected = _read_mem(EXPECTED)
    _save_png(chip, OUT_W or IMG_W, OUT_H or IMG_H, ROOT / "hwsw" / "chip_output.png")

    mismatches = 0
    first = None
    max_diff = 0
    if expected and chip:
        for index in range(min(len(expected), len(chip))):
            if chip[index] != expected[index]:
                mismatches += 1
                max_diff = max(max_diff, abs(chip[index] - expected[index]))
                if first is None:
                    first = {{"index": index, "chip": chip[index], "expected": expected[index]}}
        mismatches += abs(len(expected) - len(chip))

    payload = {{
        "bytes_received": len(chip),
        "bytes_expected": len(expected),
        "checked": bool(expected and chip),
        "match": bool(expected and chip and mismatches == 0 and len(chip) >= len(expected)),
        "mismatches": mismatches,
        "first_mismatch": first,
        "max_abs_diff": max_diff,
    }}
    VERIFY_JSON.parent.mkdir(parents=True, exist_ok=True)
    VERIFY_JSON.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Host driver for the generated chip")
    sub = parser.add_subparsers(dest="command", required=True)
    encode = sub.add_parser("encode", help="user file -> chip byte stream + expected answer")
    encode.add_argument("--input", required=True)
    encode.add_argument("--outdir", default="hwsw")
    encode.set_defaults(func=cmd_encode)
    decode = sub.add_parser("decode", help="chip bytes -> picture + comparison")
    decode.add_argument("--outdir", default="hwsw")
    decode.set_defaults(func=cmd_decode)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
'''


# --------------------------------------------------------------------------- #
# Running the pair
# --------------------------------------------------------------------------- #
def _python_env(workspace: Path) -> Dict[str, str]:
    env = dict(os.environ)
    pydeps = os.getenv("AGENT_PYDEPS_DIR") or str(
        Path(os.getenv("AGENT_ARTIFACT_ROOT",
                       os.getenv("WORKSPACE_ROOT", "/tmp/chip-orchestra/workspaces"))) / ".pydeps")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(workspace), str(workspace / "golden"), pydeps, env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    env["MPLBACKEND"] = "Agg"
    return env


def run_driver(workspace: Path, argv: List[str], timeout: int = 600) -> Tuple[int, str]:
    """Run the host driver from the workspace root. Returns (returncode, output)."""
    driver = workspace / DRIVER_REL
    if not driver.is_file():
        return 127, f"{DRIVER_REL} does not exist"
    try:
        proc = subprocess.run([sys.executable, DRIVER_REL, *argv], cwd=str(workspace),
                              env=_python_env(workspace), capture_output=True, text=True,
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"host driver timed out after {timeout}s"
    except OSError as exc:
        return 126, f"could not start the host driver: {exc}"
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or ""))[-20000:]


def _iverilog_bin() -> str:
    return os.getenv("IVERILOG_BIN", "iverilog")


def run_cosim(workspace: Path, top: str, tb_rel: str, timeout: int = 0) -> Tuple[bool, str]:
    """Compile the RTL together with the interface bench and run it.

    Returns ``(ok, log)``. ``ok`` means the simulator ran to completion — the
    VERDICT is not taken from here but from comparing the decoded bytes, because
    a bench that prints PASS while dumping nothing is exactly the failure mode
    this stage exists to catch.
    """
    timeout = timeout or int(os.getenv("HWSW_SIM_TIMEOUT_S", "2400"))
    rtl = workspace / "rtl"
    sources = [str(p.relative_to(workspace)) for p in sorted(rtl.glob("*.v"))] if rtl.is_dir() else []
    if not sources:
        return False, "no RTL sources under rtl/ to simulate"
    tb_module = Path(tb_rel).stem
    vvp_out = "hwsw/hwsw.vvp"
    (workspace / "hwsw").mkdir(parents=True, exist_ok=True)
    # A stale response from the previous input must never be mistaken for this
    # run's answer — the whole gate turns on which input produced which picture.
    for stale in (CHIP_MEM_REL, "hwsw/chip_output.png", VCD_REL):
        try:
            (workspace / stale).unlink()
        except OSError:
            pass

    log: List[str] = []
    compile_cmd = [_iverilog_bin(), "-g2012", f"-I{rtl}", "-s", tb_module, "-o", vvp_out,
                   *sources, tb_rel]
    log.append("$ " + " ".join(compile_cmd))
    try:
        proc = subprocess.run(compile_cmd, cwd=str(workspace), capture_output=True, text=True,
                              errors="replace", timeout=600)
    except subprocess.TimeoutExpired:
        return False, "\n".join(log + ["iverilog timed out while compiling the interface bench"])
    except OSError as exc:
        return False, "\n".join(log + [f"could not run iverilog: {exc}"])
    log.append((proc.stdout or "") + (proc.stderr or ""))
    if proc.returncode != 0:
        return False, "\n".join(log)

    run_cmd = ["vvp", vvp_out]
    log.append("$ " + " ".join(run_cmd))
    try:
        proc = subprocess.run(run_cmd, cwd=str(workspace), capture_output=True, text=True,
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        log.append(f"co-simulation exceeded {timeout}s and was stopped "
                   "(raise HWSW_SIM_TIMEOUT_S if the design is genuinely this slow)")
        return False, "\n".join(log)
    except OSError as exc:
        return False, "\n".join(log + [f"could not run vvp: {exc}"])
    log.append(((proc.stdout or "") + (proc.stderr or ""))[-60000:])
    return proc.returncode == 0, "\n".join(log)


# --------------------------------------------------------------------------- #
# Waveform preview
# --------------------------------------------------------------------------- #
def render_waveform(vcd_path: Path, out_png: Path, max_traces: int = 10) -> bool:
    """Draw the interface VCD as digital traces with Pillow.

    Deliberately Pillow-only: matplotlib is not a service dependency, and a
    waveform the reviewer cannot see is the difference between "the chip
    answered" and "something wrote a file"."""
    try:
        from PIL import Image, ImageDraw
    except Exception:  # noqa: BLE001
        return False
    vcd_path, out_png = Path(vcd_path), Path(out_png)
    if not vcd_path.is_file():
        return False
    try:
        # Bounded read: an interface dump is small, but never trust that.
        with vcd_path.open("r", errors="replace") as handle:
            text = handle.read(24 << 20)
    except OSError:
        return False

    names: Dict[str, str] = {}
    for ident, name in re.findall(r"\$var\s+\w+\s+\d+\s+(\S+)\s+([^\s$]+)", text):
        names.setdefault(ident, name)
    if not names:
        return False

    body = text.split("$enddefinitions", 1)[-1]
    series: Dict[str, List[Tuple[int, float]]] = {ident: [] for ident in names}
    time_now = 0
    max_time = 0
    for token in body.split():
        if token.startswith("#"):
            try:
                time_now = int(token[1:])
                max_time = max(max_time, time_now)
            except ValueError:
                pass
            continue
        if token[:1] in "01xzXZ" and len(token) > 1:
            value, ident = token[0], token[1:]
            if ident in series:
                series[ident].append((time_now, 1.0 if value == "1" else 0.0))
        elif token[:1] in "bB" and len(token) > 1:
            continue

    active = sorted((ident for ident in series if len(series[ident]) > 1),
                    key=lambda i: -len(series[i]))[:max_traces]
    if not active or max_time <= 0:
        return False

    # WINDOW the plot instead of squashing the whole run into 1000 px. This
    # design streams for 44 ms; drawn end to end, every UART frame collapses
    # into one solid green bar that shows nothing. Start where the last line to
    # wake up first moves — so every trace is live — and span far enough to
    # cover a few dozen transitions, which is a few readable frames.
    first_moves = [series[i][1][0] for i in active if len(series[i]) > 1]
    win_start = max(first_moves) if first_moves else 0
    busiest = max(active, key=lambda i: len(series[i]))
    after = [t for t, _ in series[busiest] if t >= win_start]
    win_end = after[min(len(after) - 1, 48)] if after else max_time
    if win_end <= win_start:
        win_start, win_end = 0, max_time
    span = max(1, win_end - win_start)

    width, row_h, left, top_pad = 1000, 46, 190, 34
    height = top_pad + row_h * len(active) + 22
    image = Image.new("RGB", (width, height), (14, 20, 34))
    draw = ImageDraw.Draw(image)
    draw.text((12, 6), f"Interface activity: {vcd_path.name}", fill=(200, 214, 240))
    draw.text((12, 20), f"window {win_start}..{win_end} of {max_time} ticks "
                        f"({100.0 * span / max_time:.2f}% of the run, showing individual frames)",
              fill=(120, 142, 180))
    plot_w = width - left - 24

    def level_at(points: List[Tuple[int, float]], when: int) -> float:
        value = points[0][1]
        for tick, lvl in points:
            if tick > when:
                break
            value = lvl
        return value

    for row, ident in enumerate(active):
        y0 = top_pad + row * row_h + 8
        y1 = y0 + row_h - 22
        draw.text((12, y0 + (y1 - y0) // 2 - 6), names[ident][:26], fill=(200, 214, 240))
        draw.line([(left, y1 + 4), (left + plot_w, y1 + 4)], fill=(34, 46, 70))
        points = series[ident]
        prev_x, prev_level = left, level_at(points, win_start)
        for tick, level in points:
            if tick < win_start:
                continue
            if tick > win_end:
                break
            x = left + int(plot_w * ((tick - win_start) / span))
            y = y1 if prev_level < 0.5 else y0
            draw.line([(prev_x, y), (x, y)], fill=(90, 220, 170), width=2)
            if level != prev_level:
                draw.line([(x, y0), (x, y1)], fill=(90, 220, 170), width=2)
            prev_x, prev_level = x, level
        y = y1 if prev_level < 0.5 else y0
        draw.line([(prev_x, y), (left + plot_w, y)], fill=(90, 220, 170), width=2)
    try:
        out_png.parent.mkdir(parents=True, exist_ok=True)
        image.save(out_png)
        return True
    except OSError:
        return False


def trim_vcd(workspace: Path, max_bytes: int = 48 << 20) -> None:
    """Drop an oversized interface dump once its picture has been rendered.

    A workspace that carries a multi-gigabyte VCD makes the export bundle
    undownloadable, and the waveform PNG is what the review actually reads."""
    vcd = workspace / VCD_REL
    try:
        if vcd.is_file() and vcd.stat().st_size > max_bytes:
            vcd.unlink()
    except OSError:
        pass


__all__ = [
    "DRIVER_REL", "STIMULUS_REL", "EXPECTED_MEM_REL", "CHIP_MEM_REL", "ENCODE_REL",
    "VERIFY_REL", "VCD_REL", "LOG_REL", "REPORT_REL", "ACTIVE_INPUT_REL",
    "design_constants", "top_ports", "detect_interface", "describe_interface",
    "resolve_input", "derive_testbench", "fallback_tb_source", "fallback_driver_source",
    "run_driver", "run_cosim", "render_waveform", "trim_vcd",
]
