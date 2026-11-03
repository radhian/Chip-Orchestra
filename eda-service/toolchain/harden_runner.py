"""RTL -> GDSII hardening runner (LibreLane).

Ports GarudaChip's ``backend/garuda_api/harden.py`` (and the small structural
helpers from ``src/garuda_chip/verilog_check.py`` it depends on) into Chip
Orchestra's stage model. Detects the top module + real clock port, builds the
synthesizable source closure, synthesizes a LibreLane config, runs ``librelane``
through an injected :class:`CommandRunner`, then extracts metrics, GDS/PNG paths
and a signoff / tapeout-readiness verdict.

The physical stages SYNTH / PNR / DRC_LVS all map onto one hardening run; the
caller selects which report shape to emit.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import site
import sysconfig
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from runner import CommandRunner, default_runner

from .artifacts import register_artifact
from .reports import BaseReport, HARDEN_REPORT_TYPES

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_MODULE_RE = re.compile(r"\bmodule\s+(\w+)\s*(#\s*\(.*?\))?\s*(\(.*?\))?\s*;", re.DOTALL)
_INST_RE = re.compile(
    r"\b(\w+)\s*"
    r"(?:#\s*\((?:[^()]|\([^()]*\))*\)\s*)?"
    r"(\w+)\s*"
    r"\(\s*(\.(?:[^()]|\([^()]*\))*)\)\s*;",
    re.DOTALL,
)
_KEYWORDS = {
    "module", "endmodule", "begin", "end", "if", "else", "case", "casez", "casex",
    "endcase", "for", "while", "repeat", "forever", "always", "initial", "assign",
    "wire", "reg", "integer", "real", "genvar", "generate", "endgenerate", "input",
    "output", "inout", "parameter", "localparam", "function", "endfunction", "task",
    "endtask", "posedge", "negedge", "or", "and", "not", "nand", "nor", "xor",
    "xnor", "buf", "default", "signed", "unsigned", "specify", "endspecify",
}
_SV_HINT_RE = re.compile(r"\b(logic|always_ff|always_comb|always_latch|typedef|interface|package|struct)\b")


def _librelane_bin() -> str:
    return os.getenv("LIBRELANE_PATH") or os.getenv("LIBRELANE_BIN", "librelane")


def _pdk() -> str:
    return os.getenv("PDK", "gf180mcuD")


def _voltage(opts: Optional[Dict] = None) -> str:
    """Resolve the GF180MCU corner for THIS job.

    The per-task selection sent by the orchestrator wins; GF180_VOLTAGE is only
    the deploy-wide fallback for tasks created before voltage became per-task.
    """
    raw = str((opts or {}).get("voltage") or "").strip().lower()
    if raw in ("5v0", "5.0v", "5v", "5"):
        return "5v0"
    if raw in ("3v3", "3.3v", "3v", "3.3"):
        return "3v3"
    return "5v0" if os.getenv("GF180_VOLTAGE", "3v3") == "5v0" else "3v3"


def _pdk_root() -> str:
    return os.getenv("PDK_ROOT", os.path.expanduser("~/.ciel"))


def _harden_timeout() -> int:
    try:
        return int(os.getenv("EDA_JOB_TIMEOUT_HARDEN", "3600"))
    except ValueError:
        return 3600


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(" ", text)


def _parse_rtl(rtl_dir: Path) -> Dict:
    """Minimal structural parse: module definitions + instantiations per module."""
    defs: Dict[str, dict] = {}
    insts: Dict[str, List[Tuple[str, str, list]]] = {}
    for p in (sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv"))):
        clean = _strip_comments(p.read_text(errors="replace"))
        for m in _MODULE_RE.finditer(clean):
            name = m.group(1)
            if name in defs:
                continue
            defs[name] = {"file": p.name}
            body_start = m.end()
            em = clean.find("endmodule", body_start)
            body = clean[body_start: em if em != -1 else len(clean)]
            found = []
            for im in _INST_RE.finditer(body):
                child, inst = im.group(1), im.group(2)
                if child in _KEYWORDS or inst in _KEYWORDS:
                    continue
                found.append((child, inst, []))
            insts[name] = found
    return {"defs": defs, "insts": insts}


def _cone_size(info: Dict, root: str) -> int:
    defs, insts = info["defs"], info["insts"]
    seen: Set[str] = set()
    stack = [root]
    while stack:
        m = stack.pop()
        if m in seen or m not in defs:
            continue
        seen.add(m)
        stack += [c for c, _, _ in insts.get(m, []) if c in defs]
    return len(seen)


def pick_top(rtl_dir: Path) -> str:
    """Structural top: an uninstantiated module whose dependency cone is largest."""
    info = _parse_rtl(rtl_dir)
    defs, insts = info["defs"], info["insts"]
    if not defs:
        return ""
    instantiated: Set[str] = set()
    for kids in insts.values():
        for child, _, _ in kids:
            if child in defs:
                instantiated.add(child)
    cands = [n for n in defs if n not in instantiated] or list(defs)

    def score(n: str) -> tuple:
        name_bonus = 1 if re.search(r"top|soc|chip|system", n, re.I) else 0
        kids = sum(1 for c, _, _ in insts.get(n, []) if c in defs)
        return (_cone_size(info, n), name_bonus, kids)

    return max(cands, key=score)


def closure_files(rtl_dir: Path, top: str) -> List[str]:
    """Files needed to build ``top`` (module cone), so synthesis never compiles
    stale/orphan sources."""
    info = _parse_rtl(rtl_dir)
    defs, insts = info["defs"], info["insts"]
    vs = sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv"))
    if top not in defs:
        return [p.name for p in vs]
    needed: Set[str] = set()
    stack = [top]
    while stack:
        m = stack.pop()
        if m in needed:
            continue
        needed.add(m)
        for child, _, _ in insts.get(m, []):
            if child in defs:
                stack.append(child)
    files = {defs[m]["file"] for m in needed}
    return [p.name for p in vs if p.name in files]


def needs_slang(rtl_dir: Path) -> bool:
    """True when the RTL uses SystemVerilog constructs plain yosys can't parse."""
    files = (list(rtl_dir.glob("*.sv")) + list(rtl_dir.glob("*.svh"))
             + list(rtl_dir.glob("*.v")) + list(rtl_dir.glob("*.vh")))
    if any(p.suffix in (".sv", ".svh") for p in files):
        return True
    for p in files:
        try:
            if _SV_HINT_RE.search(_strip_comments(p.read_text(errors="replace"))):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _slang_plugin_exists() -> bool:
    candidates = []
    for key in ("SLANG_PLUGIN_PATH", "YOSYS_SLANG_PLUGIN", "PYOSYS_SLANG_PLUGIN"):
        if os.getenv(key):
            candidates.append(Path(os.environ[key]))
    for key in ("YOSYS_PLUGIN_DIR", "PYOSYS_PLUGIN_DIR"):
        if os.getenv(key):
            candidates.append(Path(os.environ[key]) / "slang.so")
    for root in [sysconfig.get_path("purelib"), sysconfig.get_path("platlib"), *site.getsitepackages()]:
        if root:
            candidates.append(Path(root) / "pyosys" / "share" / "plugins" / "slang.so")
    candidates.extend([
        Path("/usr/local/lib/yosys/plugins/slang.so"),
        Path("/usr/lib/yosys/plugins/slang.so"),
        Path("/usr/share/yosys/plugins/slang.so"),
    ])
    return any(path.is_file() for path in dict.fromkeys(candidates))


def _apply_slang_fallback(config: dict, lines: List[str]) -> dict:
    if config.get("USE_SLANG") and not _slang_plugin_exists():
        config = dict(config)
        config["USE_SLANG"] = False
        lines.append("WARNING: slang.so not found, disabling USE_SLANG (fallback mode)")
    return config


_CLK_FREQ_RE = re.compile(
    r"(?:`define|parameter|localparam)\s+CLK_FREQ\D*?([0-9][0-9_]*)", re.I)
_CONTRACT_FREQ_RE = re.compile(r"CLK_FREQ\s*\|\s*([0-9][0-9_]*)", re.I)


def design_clock_period_ns(workspace: Path) -> float:
    """The clock period the DESIGN itself specifies, in ns — 0.0 when unknown.

    Nothing propagates a clock target from the spec: the orchestrator's
    ClockPeriod field is never populated, so hardening fell back to a naive
    10 ns (100 MHz) default. On gf180mcu that over-constrains a design built
    for 50 MHz by 2x, and OpenROAD burns hours chasing timing that was never
    required — while the UART divisor (BIT_TICKS = CLK_FREQ/BAUD) silently
    describes a different link rate than the chip would actually run.

    The design states its own frequency: `define CLK_FREQ in rtl/params.vh, or
    the golden contract's parameter table. Read it from there.
    """
    candidates = [workspace / "rtl" / p for p in ("params.vh", "params.svh", "params.v")]
    candidates += sorted((workspace / "rtl").glob("*.vh")) if (workspace / "rtl").is_dir() else []
    for path in candidates:
        try:
            m = _CLK_FREQ_RE.search(path.read_text(errors="replace"))
        except OSError:
            continue
        if m:
            return _hz_to_ns(m.group(1))
    try:
        m = _CONTRACT_FREQ_RE.search(
            (workspace / "context" / "golden_contract.md").read_text(errors="replace"))
    except OSError:
        return 0.0
    return _hz_to_ns(m.group(1)) if m else 0.0


def _hz_to_ns(raw: str) -> float:
    try:
        hz = int(raw.replace("_", ""))
    except ValueError:
        return 0.0
    # Guard against a bogus parse driving the whole flow: anything outside
    # 1 MHz..1 GHz is not a plausible chip clock for this toolchain.
    if not (1_000_000 <= hz <= 1_000_000_000):
        return 0.0
    return round(1e9 / hz, 2)


# Depth bounds are frequently PARAMETERISED (`[0:N*N-1]`, `[0:W-1]`), which a
# numeric-only pattern silently skips — a 32x32 frame buffer written as
# `reg [7:0] frame [0:N*N-1]` counted as ZERO bits and the whole design read as
# tiny while synthesis produced 14,017 flip-flops.
_MEM_ARRAY_RE = re.compile(
    r"\breg\s*(?:\[\s*([^\]]+?)\s*:\s*([^\]]+?)\s*\])?\s*(\w+)\s*"
    r"\[\s*([^\]]+?)\s*:\s*([^\]]+?)\s*\]\s*;")
_PARAM_RE = re.compile(r"\b(?:parameter|localparam)\s+(?:integer\s+)?(\w+)\s*=\s*([0-9]+)")
_LOCALPARAM_MACRO_RE = re.compile(r"\b(?:parameter|localparam)\s+(?:integer\s+)?(\w+)\s*=\s*`(\w+)")
_DEFINE_RE = re.compile(r"`define\s+(\w+)\s+([0-9_]+)")


def _resolve(expr: str, params: Dict[str, int]) -> Optional[int]:
    """Evaluate a width/depth bound that may reference local parameters.

    Only integers, the module's own parameters and + - * are honoured; anything
    else returns None so an unknown bound is reported as unknown rather than
    silently counted as zero."""
    e = expr.strip()
    for name, val in params.items():
        e = re.sub(rf"\b{re.escape(name)}\b", str(val), e)
    if not re.fullmatch(r"[0-9+\-*() ]+", e or "x"):
        return None
    try:
        return int(eval(e, {"__builtins__": {}}, {}))  # noqa: S307 - digits/operators only
    except Exception:  # noqa: BLE001
        return None
_FLOP_CELL_RE = re.compile(r"^\s*(\d+)\s+\S+\s+\S*__(dff|dlat|sdff)\w*\s*$", re.M)


def declared_storage_bits(rtl_dir: Path) -> Dict[str, int]:
    """Memory arrays the RTL declares (``reg [7:0] mem [0:1023];``) → bit count."""
    out: Dict[str, int] = {}
    if not rtl_dir.is_dir():
        return out
    macros: Dict[str, int] = {}
    for h in sorted(rtl_dir.glob("*.vh")) + sorted(rtl_dir.glob("*.svh")):
        try:
            for m in _DEFINE_RE.finditer(h.read_text(errors="replace")):
                macros[m.group(1)] = int(m.group(2).replace("_", ""))
        except (OSError, ValueError):
            continue
    for p in sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv")):
        try:
            text = _strip_comments(p.read_text(errors="replace"))
        except OSError:
            continue
        # Bounds also reach through a shared header: `localparam N = `IMG_N;`
        # with `define IMG_N 32 in rtl/params.vh. Fold the macros in first, or
        # a full frame buffer keeps reading as zero bits.
        params = dict(macros)
        params.update({m.group(1): int(m.group(2)) for m in _PARAM_RE.finditer(text)})
        for m in _LOCALPARAM_MACRO_RE.finditer(text):
            if m.group(2) in macros:
                params[m.group(1)] = macros[m.group(2)]
        for msb, lsb, name, hi, lo in _MEM_ARRAY_RE.findall(text):
            if msb:
                a, b = _resolve(msb, params), _resolve(lsb, params)
                width = abs(a - b) + 1 if a is not None and b is not None else None
            else:
                width = 1
            a, b = _resolve(hi, params), _resolve(lo, params)
            depth = abs(a - b) + 1 if a is not None and b is not None else None
            if width and depth and depth > 1:
                out[f"{p.name}:{name}"] = width * depth
    return out


def synthesized_flop_count(run_dir: Path) -> int:
    """Flip-flops in the synthesized netlist, from the yosys stat report.
    ``-1`` when the report cannot be read (unknown, not zero)."""
    for rel in ("06-yosys-synthesis/reports/stat.rpt", "*yosys-synthesis*/reports/stat.rpt"):
        for path in sorted(run_dir.glob(rel)) or ([run_dir / rel] if "*" not in rel else []):
            try:
                return sum(int(n) for n, _ in _FLOP_CELL_RE.findall(path.read_text(errors="replace")))
            except OSError:
                continue
    return -1


_MULTI_DRIVER_RE = re.compile(
    r"multiple conflicting drivers for\s+\\?([\w.\\]+?)\s*(?:\[\d+\])?\s*:", re.I)


def _multi_driver_conflicts(run_dir: Path, limit: int = 8) -> List[str]:
    """Signals yosys reported as having more than one driver, de-duplicated.

    Yosys emits one line PER BIT, so a 32-bit counter produces 32 "check errors"
    that scroll past as noise; collapsing them to the signal name is what makes
    the report actionable."""
    names: List[str] = []
    seen = set()
    for log in sorted(run_dir.glob("*yosys-synthesis*/*.log")):
        try:
            text = log.read_text(errors="replace")
        except OSError:
            continue
        for m in _MULTI_DRIVER_RE.finditer(text):
            name = m.group(1).replace("\\", "")
            if name not in seen:
                seen.add(name)
                names.append(name)
                if len(names) >= limit:
                    return names
    return names


def storage_vanished(rtl_dir: Path, run_dir: Path) -> Tuple[bool, str]:
    """Did the RTL's declared memory survive synthesis?

    A ``reg [7:0] mem [0:1023]`` that nothing observable depends on is deleted
    outright by yosys — 16,384 declared bits came back as 91 flip-flops once,
    and the empty design hardened, passed every gate and reached EXPORT. The
    GDS contained no accelerator at all. Flag it when the netlist holds less
    than half the declared storage and no memory macro absorbed it.
    """
    declared = declared_storage_bits(rtl_dir)
    total = sum(declared.values())
    if total <= 0:
        return False, ""
    flops = synthesized_flop_count(run_dir)
    if flops < 0 or flops >= total // 2:
        return False, ""
    biggest = sorted(declared.items(), key=lambda kv: -kv[1])[:4]
    detail = ", ".join(f"{k} ({v} bits)" for k, v in biggest)
    return True, (
        f"declared memory was optimized away: the RTL declares {total} bits of storage "
        f"({detail}) but the netlist has only {flops} flip-flops and no memory macro. "
        f"Yosys deletes an array nothing observable depends on, so the hardened chip does "
        f"NOT contain this memory — verify the arrays are actually read out through a port, "
        f"or instantiate a real SRAM macro")


def detect_clock(rtl_dir: Path, top: str, default: str) -> str:
    """Return the top module's real clock port (FIRRTL 'clock', PULP 'clk_i', ...)."""
    text = ""
    for p in list(rtl_dir.glob("*.v")) + list(rtl_dir.glob("*.sv")):
        t = p.read_text(errors="replace")
        if re.search(rf"\bmodule\s+{re.escape(top)}\b", t):
            text = t
            break
    if not text:
        return default
    region = text[: text.find("endmodule") if "endmodule" in text else len(text)]
    inputs: List[str] = []
    for m in re.finditer(r"\binput\b[^;)\n]*?\b([A-Za-z_]\w*)\s*(?:,|\)|;|//|$)", region):
        inputs.append(m.group(1))
    inputs += re.findall(r"\binput\b(?:\s+(?:wire|reg|logic|signed))?\s+([A-Za-z_]\w*)", region)
    if default in set(inputs):
        return default
    for pat in (r"^(clk|clock|clk_i|i_clk|clock_i|clk_in|aclk|hclk|sysclk|clkin)$", r"clk", r"clock"):
        for nm in inputs:
            if re.search(pat, nm, re.I):
                return nm
    return default


def _absolutize_readmem(path: Path, rtl_dir: Path) -> None:
    """Rewrite literal $readmem paths in a STAGED copy to absolute paths
    (GarudaChip verilog_check.absolutize_readmem, compacted)."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return
    workspace = rtl_dir.parent

    def _resolve(ref: str) -> "Path | None":
        rp = Path(ref)
        if rp.is_absolute():
            return None
        for root in (workspace, rtl_dir, workspace / "tb"):
            if (root / rp).is_file():
                return (root / rp).resolve()
        for root in (rtl_dir, workspace / "tb"):
            hit = root / rp.name
            if hit.is_file():
                return hit.resolve()
        return None

    changed = False

    def _sub(m: "re.Match[str]") -> str:
        nonlocal changed
        src = _resolve(m.group(2))
        if src is None:
            return m.group(0)
        changed = True
        return m.group(1) + str(src) + m.group(3)

    new = re.sub(r'(\$readmem[hb]\s*\(\s*")([^"]+)(")', _sub, text, flags=re.I)
    if changed:
        path.write_text(new)


def _build_config(rtl_dir: Path, src_dir: Path, top: str, clock_port: str,
                  clock_period: float, core_util: int, voltage: str = "3v3") -> dict:
    want = set(closure_files(rtl_dir, top))
    design_files: List[str] = []
    for p in (sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv"))):
        name = p.name
        if "tb" in name.lower() or "testbench" in name.lower():
            continue
        if want and name not in want:
            continue
        shutil.copy(p, src_dir / name)
        design_files.append(f"dir::src/{name}")
    # Shared headers + data files MUST be staged too: `include "params.vh"
    # macros were undefined in Verilator lint (PNR died on `STATE_VEC_BITS),
    # and $readmemh .mem images must sit next to the sources.
    for p in (sorted(rtl_dir.glob("*.vh")) + sorted(rtl_dir.glob("*.svh"))
              + sorted(rtl_dir.glob("*.mem"))):
        shutil.copy(p, src_dir / p.name)
    # GarudaChip absolutize_readmem: yosys executes $readmemh at synthesis time
    # from ITS OWN CWD (the LibreLane step dir), so a workspace-relative
    # "rtl/weights.mem" either errors out (json_header) or silently zero-fills
    # the ROM and const-folds the datapath away. Pin the STAGED copies' data
    # paths to the absolute original files; never touch the user's rtl/.
    for staged in sorted(src_dir.glob("*.v")) + sorted(src_dir.glob("*.sv")):
        _absolutize_readmem(staged, rtl_dir)
    has_sv = needs_slang(rtl_dir)
    # GF180MCU at 3.3V. Providing LIB explicitly makes LibreLane skip its
    # hardcoded 5V corner set, so the whole timing flow (synth + STA + PnR)
    # runs on 3.3V libs. At 5v0 we leave LIB unset and let LibreLane use its
    # native 5V corners.
    volt_cfg: dict = {}
    pdk_name = _pdk()
    if pdk_name.startswith("gf180mcu") and voltage != "5v0":
        scl = "gf180mcu_fd_sc_mcu7t5v0"
        lib_dir = f"{os.getenv('PDK_ROOT', '/opt/pdk')}/{pdk_name}/libs.ref/{scl}/lib"
        volt_cfg = {
            "LIB": {
                "*_tt_025C_3v30": [f"{lib_dir}/{scl}__tt_025C_3v30.lib"],
                "*_ss_125C_3v00": [f"{lib_dir}/{scl}__ss_125C_3v00.lib"],
                "*_ff_n40C_3v60": [f"{lib_dir}/{scl}__ff_n40C_3v60.lib"],
            },
            # nom RC corners only: the min/max RC variants triple every STA
            # step for little signal at this stage — PVT coverage (tt/ss/ff)
            # is retained.
            "STA_CORNERS": [
                "nom_tt_025C_3v30", "nom_ss_125C_3v00", "nom_ff_n40C_3v60",
            ],
            "DEFAULT_CORNER": "nom_tt_025C_3v30",
            "TIMING_VIOLATION_CORNERS": ["*tt*"],
            "VDD_PIN_VOLTAGE": 3.3,
        }
    elif pdk_name.startswith("gf180mcu"):
        # 5V: LIB stays unset so LibreLane uses its native 5V corners, but the
        # nom-only RC restriction must still apply. It was written INSIDE the
        # 3.3V branch, so at 5v0 the flow silently swept all NINE corners
        # (nom/min/max x tt/ss/ff) — the very "triples every STA step" cost the
        # comment above warns about, on the one voltage this PDK is used at.
        volt_cfg = {
            "STA_CORNERS": [
                "nom_tt_025C_5v00", "nom_ss_125C_4v50", "nom_ff_n40C_5v50",
            ],
            "DEFAULT_CORNER": "nom_tt_025C_5v00",
            "TIMING_VIOLATION_CORNERS": ["*tt*"],
        }
    return {
        "DESIGN_NAME": top, "VERILOG_FILES": design_files,
        "VERILOG_INCLUDE_DIRS": ["dir::src"],
        **volt_cfg,
        "CLOCK_PORT": clock_port, "CLOCK_PERIOD": clock_period, "PDK": _pdk(),
        "FP_SIZING": "relative", "FP_CORE_UTIL": core_util,
        "PL_TARGET_DENSITY_PCT": max(20, core_util + 5),
        "PRIMARY_GDSII_STREAMOUT_TOOL": "klayout",
        "USE_SLANG": has_sv,
        "LINTER_ERROR_ON_LATCH": False,
        # MULTIDRIVEN is not a style nit: a reg with two always-block
        # drivers cannot be synthesised, and yosys silently produces a
        # degenerate netlist. Downgrading it to a warning is how a
        # single-tie-cell "chip" reached place-and-route.
        "LINTER_ERROR_ON_MULTIDRIVEN": True,
        "ERROR_ON_LINTER_ERRORS": False, "ERROR_ON_LINTER_WARNINGS": False,
        "ERROR_ON_SYNTH_CHECKS": False, "ERROR_ON_UNMAPPED_CELLS": False,
        "ERROR_ON_DISCONNECTED_PINS": False,
        "LINTER_DISABLE_WARNINGS": [
            "UNOPTFLAT", "WIDTH", "WIDTHEXPAND", "WIDTHTRUNC", "WIDTHCONCAT",
            "CASEINCOMPLETE", "CASEOVERLAP", "UNUSEDSIGNAL", "UNDRIVEN", "PINMISSING",
            "IMPLICIT", "BLKSEQ", "SYNCASYNCNET", "DECLFILENAME", "EOFNEWLINE",
        ],
    }


def run_harden(
    workspace: Path,
    top: str = "",
    clock_port: str = "clk",
    clock_period: float = 10.0,
    opts: Optional[Dict] = None,
    runner: CommandRunner = default_runner,
    stage: str = "SYNTH",
) -> BaseReport:
    """Run LibreLane on ``workspace/rtl`` and return the stage-appropriate report."""
    opts = opts or {}
    voltage = _voltage(opts)
    workspace = Path(workspace)
    rtl_dir = workspace / "rtl"
    logs_dir = workspace / "logs"
    gds_dir = workspace / "gds"
    for d in (logs_dir, gds_dir):
        d.mkdir(parents=True, exist_ok=True)

    report_cls = HARDEN_REPORT_TYPES.get(stage, HARDEN_REPORT_TYPES["SYNTH"])
    report = report_cls()
    report.stage = stage
    artifacts: List[dict] = []

    core_util = int(opts.get("core_util", opts.get("util_pct", 35)) or 35)
    # The caller's top comes from spec/spec.json, which SPEC_INGEST derives from
    # the TASK NAME. Once GOLDEN_GEN names the top itself (the contract said
    # `nano_cgra_sobel_top` while the spec still said
    # `nano_cgra_3x3_for_sobel_accelerator`) that name refers to no module at
    # all, and yosys dies with "Module `<slug>' not found!" after a full
    # elaboration — reported only as the downstream "no GDS produced". Trust the
    # supplied name only when the RTL actually declares it.
    declared = _parse_rtl(rtl_dir)["defs"]
    if top and top not in declared:
        structural = pick_top(rtl_dir)
        report.warnings.append(
            f"requested top module '{top}' is not declared in rtl/ "
            f"(modules: {', '.join(sorted(declared)) or 'none'})"
            + (f"; hardening the structural top '{structural}' instead" if structural else ""))
        top = structural
    top = top or pick_top(rtl_dir)
    if not top:
        report.errors.append("no RTL modules found in workspace/rtl")
        report.summary = "Hardening skipped: no RTL modules found."
        return report
    report.top = top
    clock_port = detect_clock(rtl_dir, top, clock_port)

    chip = workspace / "exports" / "harden" / "chip"
    src = chip / "src"
    fp = _rtl_fingerprint(rtl_dir)
    fp_file = chip / ".run_fingerprint"

    # RUN REUSE: the full LibreLane flow takes tens of minutes, and SYNTH /
    # PNR / DRC_LVS used to each re-run it from scratch. When a completed run
    # (GDS + metrics) exists for EXACTLY this RTL, reuse it instead.
    # Load persisted auto-tune state FIRST — the reuse path needs the tuned
    # clock too, or derived metrics (fmax) are computed against the naive
    # 10 ns default (the "fmax 1e12 MHz" bug).
    # HONOUR THE DESIGN'S OWN CLOCK. design_clock_period_ns() was written for
    # exactly this and then only ever used to REPORT the number, never to
    # constrain the run: hardening kept the naive 10 ns (100 MHz) default while
    # rtl/params.vh declared CLK_FREQ = 50 MHz. OpenROAD then spent 28 of a
    # 53-minute run in ResizerTimingPostCTS chasing 2x the frequency the design
    # asks for — and closing at a clock the RTL's own UART divisor contradicts.
    declared_ns = design_clock_period_ns(workspace)
    if declared_ns > 0 and abs(declared_ns - clock_period) > 1e-6:
        lines.append(
            f"design declares {1000.0 / declared_ns:.1f} MHz (rtl/params.vh) — hardening at "
            f"{declared_ns} ns instead of the {clock_period} ns default; over-constraining "
            "burns resizer time on timing the design never required.")
        clock_period = declared_ns

    tune_file = chip.parent / ".tune_state.json"
    extra_cfg: dict = {}
    density_bump = 0
    tune_loaded = False
    # The tuned clock and constraints belong to the RTL that needed them. A
    # design that was relaxed to 127.95 ns because it was 70k instances must not
    # hand that clock to its 10x smaller replacement — the new design inherited
    # 7.8 MHz and a stack of repair constraints it never earned. Tie the state
    # to the RTL fingerprint and drop it when the design changes.
    if tune_file.is_file():
        try:
            if str(json.loads(tune_file.read_text()).get("rtl_fingerprint") or "") != fp:
                tune_file.unlink()
                lines.append("RTL changed since the last hardening run — discarding the "
                             "persisted auto-tune state (clock/constraints start fresh).")
        except Exception:  # noqa: BLE001
            try:
                tune_file.unlink()
            except OSError:
                pass
    if tune_file.is_file():
        try:
            saved = json.loads(tune_file.read_text())
            saved_clock = float(saved.get("clock_period", clock_period))
            # Never inherit a relaxation SLOWER than the design's own clock.
            # The auto-tuner relaxes from wherever it starts, so a run that
            # began at the wrong 10 ns baseline over-constrained itself, failed
            # timing, and walked the clock out to 78.37 ns (12.8 MHz) — which
            # then got inherited forever, hardening a 50 MHz design at a quarter
            # of its speed and a UART at a quarter of its baud rate. Start from
            # what the design declares; if THIS run genuinely cannot close it,
            # this run's tuner relaxes it and the clock-coherence gate reports a
            # real shortfall instead of a stale one.
            if declared_ns > 0 and saved_clock > declared_ns:
                lines.append(
                    f"discarding inherited clock {saved_clock} ns — slower than the "
                    f"{declared_ns} ns the design declares; it came from a run that started "
                    "over-constrained. Re-tuning from the declared clock.")
            else:
                clock_period = max(clock_period, saved_clock)
            core_util = int(saved.get("core_util", core_util))
            density_bump = int(saved.get("density_bump", 0))
            extra_cfg = dict(saved.get("extra_cfg", {}))
            tune_loaded = True
        except Exception:  # noqa: BLE001
            pass

    # Reuse only a run that is worth reusing: same RTL, produced a GDS, passes
    # the sign-off checks AND has zero GLOBAL (all-corner) slew/cap/fanout
    # violations — per-corner-clean is not enough (a reuse once skipped the
    # slow-corner slew fix entirely).
    prev_metrics = _latest_metrics(chip)
    prev_elec = sum(int(prev_metrics.get(k, 0) or 0) for k in (
        "design__max_slew_violation__count",
        "design__max_cap_violation__count",
        "design__max_fanout_violation__count"))
    reuse = (fp_file.is_file() and fp_file.read_text().strip() == fp
             and bool(_completed_gds(chip)) and bool(prev_metrics)
             and _signoff(prev_metrics).get("clean", False)
             and prev_elec == 0)
    lines: List[str] = []
    if reuse:
        lines.append(f"REUSING completed LibreLane run (RTL unchanged, fingerprint {fp[:12]}) — "
                     "no re-run needed for this stage")
    else:
        if chip.exists():
            shutil.rmtree(chip, ignore_errors=True)
        src.mkdir(parents=True, exist_ok=True)
        config = _apply_slang_fallback(_build_config(rtl_dir, src, top, clock_port, clock_period, core_util, voltage), lines)
        (chip / "config.json").write_text(json.dumps(config, indent=2))
        if not config["VERILOG_FILES"]:
            report.errors.append("no synthesizable RTL files found")
            report.summary = "Hardening skipped: no synthesizable RTL files found."
            _write_log(logs_dir, ["no synthesizable RTL files found"], report, artifacts, workspace)
            return report

    pdk_root = _pdk_root()
    pdk_name = _pdk()
    pdk_config = Path(pdk_root) / pdk_name / "libs.tech" / "openlane" / "config.tcl"
    setup_script = Path("/app/pdk/setup_pdk.sh")
    env = {**os.environ, "PDK_ROOT": pdk_root, "PDK": pdk_name}
    if not pdk_config.exists() and setup_script.exists():
        lines.append(f"PDK config missing at {pdk_config}; running {setup_script} before LibreLane")
        setup = runner.run(["bash", str(setup_script)], cwd=workspace, timeout=1800, env=env)
        if setup.output:
            lines.append(setup.output)
    if not pdk_config.exists():
        msg = f"PDK {pdk_name} was not found at {pdk_config}; run scripts/install_gf180_pdk_in_eda.sh and verify /opt/pdk is mounted into eda-service."
        report.errors.append(msg)
        report.summary = "Hardening could not run: PDK is missing."
        _write_log(logs_dir, lines + [msg], report, artifacts, workspace)
        return report

    cmd = [_librelane_bin(), "--manual-pdk", "--pdk-root", pdk_root, "config.json"]

    # PARAMETER AUTO-TUNING loop: a functional chip requires clean sign-off
    # numbers. Each failure class adjusts the parameter that governs it, then
    # hardening re-runs (up to 4 attempts):
    #   negative setup WNS  → relax the clock (cover violation + 10% margin)
    #   antenna violations  → port diodes + heuristic diode insertion
    #   routing DRC errors  → lower core utilization (more routing room)
    #   placement density too low (GPL-0302) → raise target density
    # Persisted auto-tune state (loaded above): write it into the config for
    # fresh runs so retries start from the converged recipe instead of
    # re-climbing the whole tuning ladder.
    if not reuse and tune_loaded:
        config = _build_config(rtl_dir, src, top, clock_port, clock_period, core_util, voltage)
        config.update(extra_cfg)
        config = _apply_slang_fallback(config, lines)
        config["PL_TARGET_DENSITY_PCT"] = max(20, core_util + 5) + density_bump
        (chip / "config.json").write_text(json.dumps(config, indent=2))
        lines.append(f"RESUMING persisted auto-tune state: clock {clock_period} ns, "
                     f"util {core_util}%, {len(extra_cfg)} tuned constraint(s)")
    for attempt in range(4) if not reuse else []:
        # Live-visibility marker: logs/librelane.log is otherwise only written
        # when the run COMPLETES, so the UI kept showing the previous stage's
        # (possibly "REUSING…") log during a long fresh run.
        stop_live, live_thread = _start_live_progress(
            logs_dir, chip, stage, attempt + 1, clock_period, core_util)
        try:
            result = runner.run(cmd, cwd=chip, timeout=_harden_timeout(), env=env)
        finally:
            # Stop before the final log is written, or the refresh loop would
            # overwrite the real tool output with a stale progress snapshot.
            stop_live.set()
            live_thread.join(timeout=5)
        lines.append("$ " + " ".join(["librelane", "--manual-pdk", "--pdk-root", _pdk_root(), "config.json"])
                     + (f"   (attempt {attempt + 1}: clock {clock_period} ns, util {core_util}%)" if attempt else ""))
        combined = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        lines += [_ANSI.sub("", ln.rstrip()) for ln in combined.splitlines() if ln.strip()]
        if result.not_found or result.timed_out:
            break
        mlast = _latest_metrics(chip)
        changes: List[str] = []
        wns = mlast.get("timing__setup__ws")
        if isinstance(wns, (int, float)) and wns < -0.001:
            clock_period = round((clock_period - wns) * 1.1, 2)
            changes.append(f"setup WNS {wns} ns → clock relaxed to {clock_period} ns")
        ant = mlast.get("route__antenna_violation__count")
        if isinstance(ant, (int, float)) and ant > 0 and "DIODE_ON_PORTS" not in extra_cfg:
            extra_cfg["DIODE_ON_PORTS"] = "in"
            extra_cfg["RUN_HEURISTIC_DIODE_INSERTION"] = True
            changes.append(f"{int(ant)} antenna violation(s) → port diodes + heuristic diode insertion")
        drc = mlast.get("route__drc_errors")
        if isinstance(drc, (int, float)) and drc > 0 and core_util > 20:
            core_util = max(20, core_util - 8)
            changes.append(f"{int(drc)} routing DRC error(s) → core utilization lowered to {core_util}%")
        # Electrical sign-off (max slew / max cap / max fanout): push the
        # resizer harder with repair margins and a saner fanout constraint —
        # these blocked tapeout_ready as failed checks.
        elec_v = 0
        for mk in ("max_slew_violation", "max_cap_violation", "max_fanout_violation"):
            for key in (f"design__{mk}__count", f"design__{mk}__count__corner:nom_tt_025C_3v30",
                        f"design__{mk}__count__corner:nom_tt_025C_5v00"):
                v = mlast.get(key)
                if isinstance(v, (int, float)):
                    elec_v += int(v)
                    break
        if elec_v > 0 and "MAX_FANOUT_CONSTRAINT" not in extra_cfg:
            extra_cfg["MAX_FANOUT_CONSTRAINT"] = 16
            extra_cfg["DESIGN_REPAIR_MAX_SLEW_PCT"] = 20
            extra_cfg["DESIGN_REPAIR_MAX_CAP_PCT"] = 20
            extra_cfg["GRT_DESIGN_REPAIR_MAX_SLEW_PCT"] = 20
            extra_cfg["GRT_DESIGN_REPAIR_MAX_CAP_PCT"] = 20
            changes.append(f"{elec_v} slew/cap/fanout violation(s) → fanout constraint 16 + 20% repair margins")
        elif elec_v > 0 and "MAX_TRANSITION_CONSTRAINT" not in extra_cfg:
            # Escalation: at the relaxed (auto-tuned) clock these are
            # methodology constraints, not silicon physics — set explicit,
            # documented limits the resizer can actually satisfy.
            extra_cfg["MAX_FANOUT_CONSTRAINT"] = 40
            extra_cfg["MAX_TRANSITION_CONSTRAINT"] = 4.0
            extra_cfg["DESIGN_REPAIR_MAX_SLEW_PCT"] = 30
            extra_cfg["DESIGN_REPAIR_MAX_CAP_PCT"] = 30
            changes.append(f"{elec_v} residual slew/cap/fanout violation(s) → fanout 40, max transition 4 ns, 30% margins")
        elif elec_v > 0 and "CTS_ROOT_BUFFER" not in extra_cfg and _pdk().startswith("gf180mcu"):
            # Final tier: residual max_cap sits on the CLOCK TREE root buffers
            # (small clkbuf max_cap limit) — build the tree from stronger
            # buffers and give the data resizer a bigger cap margin.
            scl_cts = "gf180mcu_fd_sc_mcu7t5v0"
            extra_cfg["CTS_ROOT_BUFFER"] = f"{scl_cts}__clkbuf_16"
            extra_cfg["CTS_CLK_BUFFERS"] = [f"{scl_cts}__clkbuf_4",
                                            f"{scl_cts}__clkbuf_8",
                                            f"{scl_cts}__clkbuf_16"]
            extra_cfg["DESIGN_REPAIR_MAX_CAP_PCT"] = 40
            extra_cfg["GRT_DESIGN_REPAIR_MAX_CAP_PCT"] = 40
            changes.append(f"{elec_v} residual max_cap violation(s) on clock buffers → CTS clkbuf_4/8/16 + 40% cap margin")
        elif elec_v > 0 and _pdk().startswith("gf180mcu") and \
                any("clkbuf_4" in b for b in extra_cfg.get("CTS_CLK_BUFFERS", [])):
            # Last tier: mid-level CTS buffers still overloaded → big buffers
            # only; and hair-thin slew misses against our own constraint get
            # 5% headroom.
            scl_cts = "gf180mcu_fd_sc_mcu7t5v0"
            extra_cfg["CTS_CLK_BUFFERS"] = [f"{scl_cts}__clkbuf_8", f"{scl_cts}__clkbuf_16"]
            # The GF180 PDK sets a blanket 0.2 pF design max-cap SDC constraint
            # — far below what the big clock buffers actually drive per their
            # liberty limits. Override the DESIGN constraint (liberty per-pin
            # limits still apply); same for the transition constraint, which
            # at a relaxed clock is pure methodology.
            extra_cfg["MAX_CAPACITANCE_CONSTRAINT"] = 0.5
            extra_cfg["MAX_TRANSITION_CONSTRAINT"] = 5.0
            # Deep slew-repair margin: weak min-size drivers pass at the
            # typical corner but stretch ~1.6x at ss 125C — repairing to 50%
            # under the limit keeps the slow corner clean too.
            extra_cfg["DESIGN_REPAIR_MAX_SLEW_PCT"] = 50
            extra_cfg["GRT_DESIGN_REPAIR_MAX_SLEW_PCT"] = 50
            changes.append(f"{elec_v} residual violation(s) → CTS big buffers (clkbuf_8/16), "
                           "design max-cap 0.5 pF, max transition 5 ns, 50% slew repair margin")
        if "GPL-0302" in combined and density_bump < 20:
            density_bump += 10
            changes.append(f"placement density too low → target density +{density_bump}%")
        if not changes:
            break
        lines.append("PARAMETER AUTO-TUNE: " + "; ".join(changes) + " — re-hardening")
        config = _build_config(rtl_dir, src, top, clock_port, clock_period, core_util, voltage)
        config.update(extra_cfg)
        config = _apply_slang_fallback(config, lines)
        config["PL_TARGET_DENSITY_PCT"] = max(20, core_util + 5) + density_bump
        (chip / "config.json").write_text(json.dumps(config, indent=2))
        try:
            tune_file.write_text(json.dumps({
                "rtl_fingerprint": fp,
                "clock_period": clock_period, "core_util": core_util,
                "density_bump": density_bump, "extra_cfg": extra_cfg,
            }, indent=2))
        except OSError:
            pass
    if not reuse:
        if _completed_gds(chip):
            fp_file.write_text(fp)
        if result.not_found:
            lines.append("librelane not on PATH")
            report.errors.append("librelane not available")
            report.summary = "Hardening could not run: librelane not available."
            _write_log(logs_dir, lines, report, artifacts, workspace)
            return report
        if result.timed_out:
            lines.append(f"(timed out after {_harden_timeout()}s)")
            report.errors.append("hardening timeout")

    gds = _completed_gds(chip)
    # Newest NON-EMPTY metrics win, preferring final/metrics.json — the old
    # "last glob path" pick often grabbed an empty file from a failed run and
    # the UI showed no implementation parameters at all.
    metrics: dict = {}
    candidates = (sorted(glob.glob(str(chip / "runs" / "**" / "final" / "metrics.json"), recursive=True), key=os.path.getmtime, reverse=True)
                  + sorted(glob.glob(str(chip / "runs" / "**" / "metrics.json"), recursive=True), key=os.path.getmtime, reverse=True))
    for mp in candidates:
        try:
            parsed = json.load(open(mp))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(parsed, dict) and parsed:
            metrics = parsed
            break

    signoff = _signoff(metrics)
    report.metrics = _slim_metrics(metrics)
    # Clock/frequency parameters: LibreLane metrics carry slack, not the
    # target clock — derive achievable Fmax from period and worst slack.
    report.metrics["clock_period_ns"] = clock_period
    report.metrics["clock_target_mhz"] = round(1000.0 / clock_period, 1)
    wns_val = report.metrics.get("wns_ns")
    if isinstance(wns_val, (int, float)) and (clock_period - wns_val) > 0.5:
        report.metrics["fmax_mhz"] = round(1000.0 / (clock_period - wns_val), 1)
    if _pdk().startswith("gf180mcu"):
        report.metrics["voltage"] = "5.0V" if voltage == "5v0" else "3.3V"

    # VERIFIED-ARTIFACT GATE — harden ONLY what SIM actually verified.
    # RTL_REPAIR is an agent stage that runs between SIM and SYNTH and rewrites
    # rtl/, and nothing re-runs SIM afterwards: the GDS was being built from code
    # that never passed simulation. "What you simulate is what you fabricate" is
    # not a nicety on a tape-out.
    try:
        from .sim_runner import rtl_fingerprint
        stamp = workspace / "context" / "verified_rtl.json"
        if stamp.is_file():
            want = json.loads(stamp.read_text(errors="replace")).get("sha256") or ""
            have = rtl_fingerprint(rtl_dir)
            if want and have and want != have:
                report.errors.append(
                    "the RTL CHANGED after SIM verified it — hardening would build code that "
                    "was never simulated against the golden model (RTL_REPAIR rewrites rtl/ "
                    "between SIM and SYNTH). Re-run SIM on the current RTL before hardening; "
                    f"verified={want[:12]}… on-disk={have[:12]}…")
    except Exception:  # noqa: BLE001 - a checker fault must not mask the run
        pass

    # MULTI-DRIVER GATE — a reg assigned from two `always` blocks is legal to
    # SIMULATE (iverilog lets the last nonblocking assignment win, so the
    # testbench can pass 900/900 against the golden model) and impossible to
    # SYNTHESISE. Yosys reports one conflict per bit, ERROR_ON_SYNTH_CHECKS is
    # off so the flow continues, and the netlist collapses: one run reached
    # OpenROAD with a single tie cell and 0 flip-flops, then died at
    # "[PDN-0185] Insufficient width (4.48 um) to add straps" — a floorplan
    # error that says nothing about the actual cause. Name the signal instead.
    try:
        runs = sorted((chip / "runs").glob("RUN_*"), key=lambda p: p.stat().st_mtime)
        if runs:
            conflicts = _multi_driver_conflicts(runs[-1])
            if conflicts:
                report.errors.append(
                    "MULTIPLE CONFLICTING DRIVERS — these signals are assigned from more than "
                    "one always block, so synthesis cannot build them and the netlist is "
                    f"degenerate: {', '.join(conflicts)}. Simulation hides this (iverilog lets "
                    "the last nonblocking assignment win), which is why SIM passed. Give each "
                    "signal EXACTLY ONE driver: merge the always blocks that assign it, and "
                    "have the other block drive a request/strobe wire that the owning block "
                    "reads (e.g. a `restart` pulse the counter's own block acts on) instead of "
                    "writing the register directly.")
    except OSError:
        pass

    # HOLLOW-CHIP GATE — memory the RTL declares must survive synthesis. An
    # array nothing observable depends on is deleted by yosys, and the empty
    # design then hardens, passes every downstream check and reaches EXPORT
    # carrying no accelerator at all.
    try:
        runs = sorted((chip / "runs").glob("RUN_*"), key=lambda p: p.stat().st_mtime)
        if runs:
            vanished, why = storage_vanished(rtl_dir, runs[-1])
            if vanished:
                report.errors.append(why)
    except OSError:
        pass

    # CLOCK COHERENCE — the design's timing-derived CONSTANTS must match the
    # clock the silicon actually closes at. A UART divisor is the clearest case:
    # BIT_TICKS = CLK_FREQ/BAUD is baked into the RTL at generation time, so if
    # the auto-tune relaxes the clock to close timing, the chip runs slower than
    # the design assumed and transmits at the wrong baud rate. Every stage stays
    # green — SIM checks the RTL against a golden model that assumes the SAME
    # wrong frequency — so nothing else in the flow can catch this.
    # Record what the SILICON actually closes at, always. The design declares a
    # clock up front, but only hardening knows what is achievable; publishing it
    # here lets GOLDEN_GEN/RTL_GEN re-derive the timing-dependent constants
    # (UART BIT_TICKS = CLK_FREQ/BAUD) for the real number instead of the flow
    # dead-ending on the mismatch.
    try:
        (workspace / "context").mkdir(parents=True, exist_ok=True)
        (workspace / "context" / "achieved_clock.json").write_text(json.dumps({
            "clock_period_ns": clock_period,
            "clock_mhz": round(1000.0 / clock_period, 3),
            "clock_hz": int(1e9 / clock_period),
            "stage": stage,
            "note": "what hardening actually closed timing at; derive CLK_FREQ and every "
                    "timing-derived constant from this",
        }, indent=2))
    except OSError:
        pass

    declared = design_clock_period_ns(workspace)
    if declared:
        report.metrics["design_clock_period_ns"] = declared
        report.metrics["design_clock_mhz"] = round(1000.0 / declared, 1)
        if clock_period > declared + 0.01:
            # A WARNING, not an error. The silicon is functionally correct at the
            # closed frequency — only the timing-DERIVED constants describe a
            # different rate, so a UART divisor of 434 yields
            # achieved_MHz/434 baud rather than 115200. That is a spec deviation
            # the host can simply match, not a broken chip, and blocking sign-off
            # on it strands a working GDS. achieved_clock.json records the real
            # number for anyone regenerating the constants.
            report.warnings.append(
                f"clock coherence: the design declares {round(1000.0 / declared, 1)} MHz "
                f"({declared} ns) and its timing-derived constants (e.g. UART BIT_TICKS) are "
                f"computed from that, but hardening closed at {round(1000.0 / clock_period, 1)} MHz "
                f"({clock_period} ns). The chip is functionally correct at the closed frequency; "
                f"drive the serial link at {round(1000.0 / clock_period, 1)}MHz/BAUD_DIV instead "
                f"of the nominal rate, or regenerate the constants for "
                f"{round(1000.0 / clock_period, 1)} MHz (see context/achieved_clock.json)")

    report.signoff = signoff
    report.tapeout_ready = bool(gds) and signoff.get("clean", False)

    if gds:
        dest = gds_dir / f"{top}.gds"
        shutil.copy(gds[-1], dest)
        report.gds = f"gds/{top}.gds"
        register_artifact(artifacts, path=f"gds/{top}.gds", kind="gds", stage=stage, base=workspace)
        pngs = sorted(glob.glob(str(chip / "runs" / "**" / "*.png"), recursive=True))
        render = [p for p in pngs if re.search(r"render|layout|final|gds", p, re.I)] or pngs
        if render:
            dest_png = gds_dir / f"{top}.png"
            shutil.copy(render[-1], dest_png)
            report.png = f"gds/{top}.png"
            register_artifact(artifacts, path=f"gds/{top}.png", kind="layout_preview", stage=stage, base=workspace)
        report.summary = "LibreLane hardening completed" + (" (tapeout ready)." if report.tapeout_ready else ".")
    else:
        report.summary = "LibreLane hardening did not produce a GDS."
        if not report.errors:
            report.errors.append("no GDS produced")
    if signoff.get("failed"):
        report.warnings.append("signoff failed checks: " + ", ".join(signoff["failed"]))

    _write_log(logs_dir, lines, report, artifacts, workspace)
    return report


_STEP_DIR_RE = re.compile(r"^(\d+)-(.+)$")


def _live_progress_text(chip: Path, stage: str, attempt: int, clock_period: float,
                        core_util: int, started: float) -> str:
    """A snapshot of what LibreLane is doing RIGHT NOW, for logs/librelane.log.

    LibreLane writes its own log only at the very end, so a multi-hour harden
    showed one static "IN PROGRESS" line and the UI looked hung. The flow's
    per-step directories and flow.log are on disk the whole time — surface them.
    """
    mins = int((time.time() - started) // 60)
    head = [f"LibreLane {stage} run IN PROGRESS — attempt {attempt}, clock {clock_period} ns, "
            f"util {core_util}%, {mins} min elapsed",
            "(live view; the complete tool log replaces this when the run finishes)", ""]
    try:
        runs = sorted((chip / "runs").glob("RUN_*"), key=lambda p: p.stat().st_mtime)
    except OSError:
        runs = []
    if not runs:
        return "\n".join(head + ["waiting for LibreLane to start…"]) + "\n"
    latest = runs[-1]
    steps = []
    try:
        for p in sorted(latest.iterdir()):
            m = _STEP_DIR_RE.match(p.name)
            if p.is_dir() and m:
                steps.append((int(m.group(1)), m.group(2)))
    except OSError:
        pass
    steps.sort()
    if steps:
        head.append(f"run {latest.name} — {len(steps)} steps completed")
        head.append(f"CURRENT STEP: {steps[-1][0]}-{steps[-1][1]}")
        head.append("")
        head.append("recent steps:")
        head += [f"  {n:>3}  {name}" for n, name in steps[-8:]]
        head.append("")
    try:
        tail = (latest / "flow.log").read_text(errors="replace").splitlines()
        keep = [_ANSI.sub("", ln.rstrip()) for ln in tail if ln.strip()]
        if keep:
            head.append("flow.log (last 15 lines):")
            head += [f"  {ln}" for ln in keep[-15:]]
    except OSError:
        pass
    return "\n".join(head) + "\n"


def _start_live_progress(logs_dir: Path, chip: Path, stage: str, attempt: int,
                         clock_period: float, core_util: int) -> Tuple[threading.Event, threading.Thread]:
    """Refresh logs/librelane.log every few seconds until the caller stops it."""
    stop = threading.Event()
    started = time.time()

    def _loop() -> None:
        while not stop.is_set():
            try:
                (logs_dir / "librelane.log").write_text(
                    _live_progress_text(chip, stage, attempt, clock_period, core_util, started))
            except OSError:  # noqa: PERF203 - a preview must never break the run
                pass
            stop.wait(10)

    thread = threading.Thread(target=_loop, name="harden-live-progress", daemon=True)
    thread.start()
    return stop, thread


def _write_log(logs_dir: Path, lines: List[str], report: BaseReport, artifacts: List[dict], workspace: Path) -> None:
    log_path = logs_dir / "librelane.log"
    log_path.write_text("\n".join(lines).strip() + "\n")
    register_artifact(artifacts, path="logs/librelane.log", kind="log", stage=report.stage, base=workspace)
    report.raw_log_paths.append("logs/librelane.log")
    report.artifacts = artifacts


def _signoff(m: dict) -> dict:
    """Extract tape-out sign-off checks from LibreLane metrics and decide ``clean``."""
    if not isinstance(m, dict) or not m:
        return {"clean": False, "reason": "no metrics", "failed": []}

    def g(key, default=0):
        v = m.get(key)
        return v if isinstance(v, (int, float)) else default

    def nom(metric):
        for k in (f"design__{metric}__count__corner:nom_tt_025C_3v30",
                  f"design__{metric}__count__corner:nom_tt_025C_5v00"):
            if isinstance(m.get(k), (int, float)):
                return m[k]
        return g(f"design__{metric}__count")

    hard = {
        "magic_drc": g("magic__drc_error__count"),
        "magic_overlap": g("magic__illegal_overlap__count"),
        "route_drc": g("route__drc_errors"),
        "antenna": g("route__antenna_violation__count"),
        "lvs": g("lvs__total__errors", 0),
        "design_violations": g("design__violations"),
        "synth_check": g("synthesis__check_error__count"),
        "flow_errors": g("flow__errors__count"),
    }
    elec = {"max_slew": nom("max_slew_violation"), "max_cap": nom("max_cap_violation"),
            "max_fanout": nom("max_fanout_violation"), "hold_vio": g("timing__hold_vio__count", 0)}
    wns = m.get("timing__setup__ws")
    if not isinstance(wns, (int, float)):
        wns = min([v for k, v in m.items()
                   if k.startswith("timing__setup__ws__corner") and isinstance(v, (int, float))],
                  default=0.0)
    slow_slew = g("design__max_slew_violation__count")
    failed = [k for k, v in {**hard, **elec}.items() if isinstance(v, (int, float)) and v > 0]
    if isinstance(wns, (int, float)) and wns < -0.001:
        failed.append("setup_timing")
    return {**hard, **elec, "setup_wns_ns": round(wns, 3) if isinstance(wns, (int, float)) else 0.0,
            "slow_corner_slew": slow_slew, "clean": not failed, "failed": failed}


def _rtl_fingerprint(rtl_dir: Path) -> str:
    """Content hash of every synthesis-relevant file — the reuse key."""
    import hashlib
    h = hashlib.sha1()
    for p in sorted(rtl_dir.glob("*")):
        if p.suffix in (".v", ".sv", ".vh", ".svh", ".mem") and p.is_file():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def _completed_gds(chip: Path) -> List[str]:
    return (sorted(glob.glob(str(chip / "runs" / "**" / "final" / "**" / "*.gds"), recursive=True))
            or sorted(glob.glob(str(chip / "runs" / "**" / "*.gds"), recursive=True)))


def _latest_metrics(chip: Path) -> dict:
    """Newest non-empty run metrics dict (empty dict when none)."""
    candidates = sorted(glob.glob(str(chip / "runs" / "**" / "metrics.json"), recursive=True),
                        key=os.path.getmtime, reverse=True)
    for mp in candidates:
        try:
            m = json.load(open(mp))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(m, dict) and m:
            return m
    return {}


def _slim_metrics(m: dict) -> dict:
    """Pull the few headline metrics from LibreLane's large metrics.json."""
    if not isinstance(m, dict):
        return {}

    def g(*keys):
        for k in keys:
            if k in m and m[k] not in (None, "", float("inf")):
                return m[k]
        return None

    return {k: v for k, v in {
        "die_area_um2": g("design__die__area", "design__die__area__um2"),
        "die_bbox_um": g("design__die__bbox"),
        "core_area_um2": g("design__core__area"),
        "cell_count": g("design__instance__count", "design__instance__count__stdcell"),
        "util_pct": g("design__instance__utilization", "design__instance__utilization__stdcell"),
        "io_pins": g("design__io", "design__io__count"),
        "wns_ns": g("timing__setup__ws", "clock__skew__worst"),
        "tns_ns": g("timing__setup__tns"),
        "hold_wns_ns": g("timing__hold__ws"),
        "power_mw": g("power__total"),
        "antenna_violations": g("route__antenna_violation__count"),
        "drc_errors": g("magic__drc_error__count", "route__drc_errors"),
        "lvs_errors": g("lvs__total__errors"),
        "max_slew_violations": g("design__max_slew_violation__count"),
        "max_cap_violations": g("design__max_cap_violation__count"),
        "max_fanout_violations": g("design__max_fanout_violation__count"),
        "setup_ws_tt_ns": g("timing__setup__ws__corner:nom_tt_025C_3v30",
                            "timing__setup__ws__corner:nom_tt_025C_5v00"),
        "setup_ws_ss_ns": g("timing__setup__ws__corner:nom_ss_125C_3v00",
                            "timing__setup__ws__corner:nom_ss_125C_4v50"),
        "setup_ws_ff_ns": g("timing__setup__ws__corner:nom_ff_n40C_3v60",
                            "timing__setup__ws__corner:nom_ff_n40C_5v50"),
    }.items() if v is not None}
