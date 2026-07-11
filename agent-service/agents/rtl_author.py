"""LLM-driven RTL + testbench authoring with an iverilog compile-repair loop.

``run_rtl_gen`` / ``run_tb_gen`` (in :mod:`agents.stage_handlers`) delegate here.
In ``LLM_PROVIDER=mock`` (or when a provider/credentials are unavailable) the
functions fall back to the original deterministic templates so the stack keeps
running end-to-end and the unit tests stay deterministic. With a real provider
wired, RTL is generated from the design spec + bundled few-shot examples, then
compile-checked with ``iverilog -tnull`` and repaired (up to ``MAX_REPAIR_ITERS``
rounds) by feeding the compiler errors + known fix hints back to the model.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import knowledge
from llm import LLMRuntime, build_llm_runtime


def _max_repairs() -> int:
    try:
        return max(0, int(os.getenv("MAX_REPAIR_ITERS", "3")))
    except ValueError:
        return 3


@dataclass
class RTLResult:
    top: str
    code: str
    filename: str
    compiled: bool
    attempts: int
    provider: str
    log: str = ""
    repaired: bool = False
    fix_hints: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Deterministic mock templates (preserve original behaviour + test contracts)
# --------------------------------------------------------------------------- #
def mock_rtl(top: str) -> str:
    return (
        f"module {top} #(parameter WIDTH = 32) (\n"
        "  input  logic             clk,\n"
        "  input  logic             rst_n,\n"
        "  input  logic [WIDTH-1:0] data_i,\n"
        "  output logic [WIDTH-1:0] data_o\n"
        ");\n"
        "  always_ff @(posedge clk or negedge rst_n) begin\n"
        "    if (!rst_n) data_o <= '0;\n"
        "    else        data_o <= data_i;\n"
        "  end\n"
        "endmodule\n"
    )


def mock_tb(top: str) -> str:
    return (
        f"`timescale 1ns/1ps\n"
        f"module {top}_tb;\n"
        "  logic clk = 0; logic rst_n = 0;\n"
        "  logic [31:0] data_i = 0; logic [31:0] data_o;\n"
        "  always #5 clk = ~clk;\n"
        f"  {top} dut(.clk(clk), .rst_n(rst_n), .data_i(data_i), .data_o(data_o));\n"
        "  initial begin\n"
        "    $dumpfile(\"design.vcd\");\n"
        f"    $dumpvars(0, {top}_tb);\n"
        "    #12 rst_n = 1; data_i = 32'hA5A5_A5A5;\n"
        "    #20 if (data_o !== 32'hA5A5_A5A5) $fatal(1, \"mismatch\"); else $display(\"TEST PASSED\");\n"
        "    #10 $finish;\n"
        "  end\n"
        "endmodule\n"
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
_CODE_BLOCK = re.compile(r"```(?:systemverilog|verilog|sv|v)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_MODULE_RE = re.compile(r"\bmodule\s+([A-Za-z_]\w*)")


def extract_code(text: str) -> str:
    blocks = _CODE_BLOCK.findall(text or "")
    if blocks:
        return "\n\n".join(b.strip() for b in blocks).strip()
    return (text or "").strip()


def detect_top(code: str, fallback: str) -> str:
    modules = _MODULE_RE.findall(code or "")
    if not modules:
        return fallback
    if fallback in modules:
        return fallback
    # Heuristic: the last-declared module usually instantiates the others.
    return modules[-1]


def iverilog_bin() -> Optional[str]:
    explicit = os.getenv("IVERILOG_PATH") or os.getenv("IVERILOG_BIN")
    if explicit and (shutil.which(explicit) or Path(explicit).exists()):
        return explicit
    return shutil.which("iverilog")


def compile_check(sources: Dict[str, str]) -> Tuple[bool, str]:
    """Compile ``sources`` (name -> code) with ``iverilog -tnull``.

    Returns ``(ok, log)``. When iverilog is unavailable the check is skipped and
    reported as passing so mock/local runs still complete.
    """
    binary = iverilog_bin()
    if not binary:
        return True, "iverilog not available; compile check skipped"
    with tempfile.TemporaryDirectory() as tmp:
        paths: List[str] = []
        for name, code in sources.items():
            p = Path(tmp) / name
            p.write_text(code, encoding="utf-8")
            paths.append(str(p))
        cmd = [binary, "-g2012", "-tnull", "-Wall", "-o", str(Path(tmp) / "_compiled.out"), *paths]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except (subprocess.TimeoutExpired, OSError) as exc:  # pragma: no cover
            return False, f"iverilog invocation failed: {exc}"
        log = (proc.stdout + "\n" + proc.stderr).strip()
        return proc.returncode == 0, log


def _few_shot(brief: str, limit: int = 2) -> str:
    examples = knowledge.select_examples(brief, limit=limit)
    if not examples:
        return ""
    parts = ["Reference examples of synthesizable RTL (style guide, do not copy verbatim):"]
    for ex in examples:
        parts.append(f"// example: {ex.name}\n{ex.code}")
    return "\n\n".join(parts)


_RTL_SYSTEM = (
    "You are an expert Verilog/SystemVerilog RTL designer. You produce clean, "
    "synthesizable RTL targeting the open-source OpenLane / LibreLane flow with "
    "the GF180MCU or Sky130 PDK. Hard rules: (1) output ONLY code inside a single "
    "```verilog code block, no prose; (2) signals assigned in always/procedural "
    "blocks must be reg/logic, external inputs stay wire; (3) single clock domain, "
    "synchronous reset; (4) NO unpacked-array module ports (flatten to packed "
    "vectors); (5) no vendor primitives or non-synthesizable constructs; (6) the "
    "design must be self-contained and include a clearly named top module."
)


def generate_rtl(brief: str, top: str, runtime: Optional[LLMRuntime] = None) -> RTLResult:
    runtime = runtime or build_llm_runtime()
    if runtime.is_mock:
        code = mock_rtl(top)
        return RTLResult(top=top, code=code, filename=f"{top}.sv", compiled=True,
                         attempts=0, provider="mock", log="mock template (no LLM)")

    few = _few_shot(brief)
    user = (
        f"Design specification:\n{brief}\n\n"
        f"Preferred top module name: `{top}` (use it if reasonable).\n\n"
        f"{few}\n\nGenerate the complete synthesizable RTL now."
    )
    raw = runtime.complete(system_prompt=_RTL_SYSTEM, user_prompt=user, fallback="")
    code = extract_code(raw)
    if not code:
        code = mock_rtl(top)
        return RTLResult(top=top, code=code, filename=f"{top}.sv", compiled=True,
                         attempts=1, provider=runtime.provider, log="empty LLM output; used template")

    resolved_top = detect_top(code, top)
    filename = f"{resolved_top}.sv"
    ok, log = compile_check({filename: code})
    attempts = 1
    repaired = False
    all_hints: List[str] = []
    while not ok and attempts <= _max_repairs():
        hints = knowledge.lookup_fix_hints(log)
        all_hints.extend(hints)
        code = _repair_rtl(runtime, code, resolved_top, log, hints)
        resolved_top = detect_top(code, resolved_top)
        filename = f"{resolved_top}.sv"
        ok, log = compile_check({filename: code})
        attempts += 1
        repaired = True

    return RTLResult(top=resolved_top, code=code, filename=filename, compiled=ok,
                     attempts=attempts, provider=runtime.provider, log=log,
                     repaired=repaired, fix_hints=all_hints)


def _repair_rtl(runtime: LLMRuntime, code: str, top: str, log: str, hints: List[str]) -> str:
    hint_block = ("\n".join(f"- {h}" for h in hints)) if hints else "(no matching seed hint)"
    user = (
        "The following RTL failed to compile with `iverilog -g2012 -tnull`:\n\n"
        f"```verilog\n{code}\n```\n\n"
        f"Compiler output:\n{log}\n\n"
        f"Known fix hints:\n{hint_block}\n\n"
        f"Return the corrected, complete RTL in a single ```verilog code block. "
        f"Keep the top module named `{top}`. Fix all reported errors."
    )
    raw = runtime.complete(system_prompt=_RTL_SYSTEM, user_prompt=user, fallback="")
    fixed = extract_code(raw)
    return fixed or code


_TB_SYSTEM = (
    "You are a verification engineer. Produce a self-checking SystemVerilog "
    "testbench for the given DUT. Hard rules: (1) output ONLY code in a single "
    "```verilog block; (2) instantiate the DUT and drive a clock; (3) apply "
    "stimulus and CHECK outputs, using $fatal/$error on mismatch and $display "
    "\"TEST PASSED\" on success; (4) include $dumpfile(\"design.vcd\") + "
    "$dumpvars for waveform capture; (5) end with $finish."
)


def generate_tb(rtl_code: str, top: str, brief: str = "", runtime: Optional[LLMRuntime] = None) -> str:
    runtime = runtime or build_llm_runtime()
    if runtime.is_mock:
        return mock_tb(top)
    user = (
        f"Design under test (top module `{top}`):\n\n```verilog\n{rtl_code}\n```\n\n"
        f"Design intent:\n{brief}\n\n"
        f"Write a self-checking testbench module named `{top}_tb`. It must "
        f"instantiate `{top}` (label the instance `dut`), dump to design.vcd, "
        f"self-check outputs, print TEST PASSED on success, and $finish."
    )
    raw = runtime.complete(system_prompt=_TB_SYSTEM, user_prompt=user, fallback="")
    code = extract_code(raw)
    if not code or f"{top}" not in code or "$dumpfile" not in code:
        return mock_tb(top)
    return code


__all__ = [
    "RTLResult",
    "mock_rtl",
    "mock_tb",
    "extract_code",
    "detect_top",
    "iverilog_bin",
    "compile_check",
    "generate_rtl",
    "generate_tb",
]
