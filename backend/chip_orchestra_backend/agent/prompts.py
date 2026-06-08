"""Prompt templates for the agent nodes.

Adapted from GarudaChip's generator/decomposer/testbench/corrector prompts,
including the synthesis "pitfall" warnings that keep local models producing
clean, simulatable Verilog.
"""

PITFALLS = """\
Avoid these common Verilog pitfalls:
- Do not use unsupported replication/concatenation syntax; size every bus explicitly.
- Declare vector widths on every port, reg, and wire; never rely on implicit 1-bit nets.
- Drive each signal from exactly one always/assign block (no multiple drivers).
- Use non-blocking (<=) assignments in sequential always @(posedge clk) blocks.
- Keep the design fully synthesizable: no initial blocks in RTL, no delays (#), no $display in RTL.
- Reset all sequential state on the reset condition.
"""

PLAN_PROMPT = """\
You are a senior digital design architect. A user wants this hardware block:

\"\"\"{brief}\"\"\"

Write a short, concrete build plan (5-8 bullet points) covering: the top-level
module name, key ports, internal datapath/FSM, clocking/reset strategy, and the
main verification checks. Be specific and synthesis-minded. Plain text, no code.
"""

GENERATE_PROMPT = """\
You are an expert Verilog RTL engineer. Generate synthesizable Verilog-2001/2012
for the following design brief.

Design brief:
\"\"\"{brief}\"\"\"

Build plan to follow:
{plan}
{reference}
{pitfalls}

Requirements:
- Decompose the design into MULTIPLE modules where natural — a top module that
  instantiates submodules (e.g. datapath, control/FSM, register file, ALU, decoder).
- Define every module in the SAME response (one ```verilog block containing several
  `module … endmodule` definitions). Each module becomes its own file.
- Use a clear top module name derived from the design, and define the top module LAST.
- Synchronous design with `clk` and active-low `rst_n` unless the brief says otherwise.
- Output ONLY a single ```verilog code block. No prose.
"""

DECOMPOSE_PROMPT = """\
Split the following Verilog into one file per module, plus a shared header file
if there are common parameters/macros. Respond with ONLY a JSON object mapping
filename -> file contents, e.g.:
{{"alu.v": "module alu ...", "top.v": "module top ..."}}

Use `.v` for modules and `.vh` for headers. Keep code identical except for the split.

Verilog:
```verilog
{verilog}
```
"""

TESTBENCH_PROMPT = """\
Write a self-checking Verilog testbench for the module `{top}` below.

Requirements:
- Instantiate `{top}`, drive clock and reset, apply meaningful stimulus.
- Check outputs against expected values; count errors.
- Print exactly "Result: PASSED" if all checks pass, otherwise "Result: FAILED".
- Dump waves: `$dumpfile("{top}.vcd"); $dumpvars(0, tb);` and name the testbench module `tb`.
- End simulation with `$finish`.
- Output ONLY a single ```verilog code block.

Module under test:
```verilog
{rtl}
```
"""

FIX_DESIGN_PROMPT = """\
The Verilog design failed simulation. Fix the RTL so the testbench passes.

Simulation / compile output:
```
{sim_output}
```

Current RTL:
```verilog
{rtl}
```
{pitfalls}
Output ONLY the corrected, complete RTL in a single ```verilog code block. No prose.
"""

FIX_TB_PROMPT = """\
The testbench appears to be at fault (the RTL looks correct for the brief).
Rewrite the self-checking testbench for `{top}` so it correctly verifies the design.

Simulation output:
```
{sim_output}
```

RTL under test:
```verilog
{rtl}
```

Keep the "Result: PASSED" / "Result: FAILED" convention and dump a VCD.
Output ONLY a single ```verilog code block.
"""

ROUTE_PROMPT = """\
A Verilog simulation failed. Decide whether the DESIGN (RTL) or the TESTBENCH is
more likely at fault, given the brief and the output. Answer with one word only:
DESIGN or TESTBENCH.

Brief: {brief}

Simulation output:
```
{sim_output}
```
"""
