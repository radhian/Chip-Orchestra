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


def _build_config(rtl_dir: Path, src_dir: Path, top: str, clock_port: str,
                  clock_period: float, core_util: int) -> dict:
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
    has_sv = needs_slang(rtl_dir)
    return {
        "DESIGN_NAME": top, "VERILOG_FILES": design_files,
        "CLOCK_PORT": clock_port, "CLOCK_PERIOD": clock_period, "PDK": _pdk(),
        "FP_SIZING": "relative", "FP_CORE_UTIL": core_util,
        "PL_TARGET_DENSITY_PCT": max(20, core_util + 5),
        "PRIMARY_GDSII_STREAMOUT_TOOL": "klayout",
        **({"USE_SLANG": True} if has_sv else {}),
        "LINTER_ERROR_ON_LATCH": False, "LINTER_ERROR_ON_MULTIDRIVEN": False,
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
    top = top or pick_top(rtl_dir)
    if not top:
        report.errors.append("no RTL modules found in workspace/rtl")
        report.summary = "Hardening skipped: no RTL modules found."
        return report
    report.top = top
    clock_port = detect_clock(rtl_dir, top, clock_port)

    chip = workspace / "exports" / "harden" / "chip"
    src = chip / "src"
    if chip.exists():
        shutil.rmtree(chip, ignore_errors=True)
    src.mkdir(parents=True, exist_ok=True)
    config = _build_config(rtl_dir, src, top, clock_port, clock_period, core_util)
    (chip / "config.json").write_text(json.dumps(config, indent=2))
    if not config["VERILOG_FILES"]:
        report.errors.append("no synthesizable RTL files found")
        report.summary = "Hardening skipped: no synthesizable RTL files found."
        _write_log(logs_dir, ["no synthesizable RTL files found"], report, artifacts, workspace)
        return report

    cmd = [_librelane_bin(), "--manual-pdk", "--pdk-root", _pdk_root(), "config.json"]
    env = {**os.environ, "PDK_ROOT": _pdk_root()}
    result = runner.run(cmd, cwd=chip, timeout=_harden_timeout(), env=env)
    lines: List[str] = ["$ " + " ".join(["librelane", "--manual-pdk", "--pdk-root", _pdk_root(), "config.json"])]
    combined = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    lines += [_ANSI.sub("", ln.rstrip()) for ln in combined.splitlines() if ln.strip()]
    if result.not_found:
        lines.append("librelane not on PATH")
        report.errors.append("librelane not available")
        report.summary = "Hardening could not run: librelane not available."
        _write_log(logs_dir, lines, report, artifacts, workspace)
        return report
    if result.timed_out:
        lines.append(f"(timed out after {_harden_timeout()}s)")
        report.errors.append("hardening timeout")

    gds = (sorted(glob.glob(str(chip / "runs" / "**" / "final" / "**" / "*.gds"), recursive=True))
           or sorted(glob.glob(str(chip / "runs" / "**" / "*.gds"), recursive=True)))
    metrics: dict = {}
    for mp in glob.glob(str(chip / "runs" / "**" / "metrics.json"), recursive=True):
        try:
            metrics = json.load(open(mp))
        except Exception:  # noqa: BLE001
            pass

    signoff = _signoff(metrics)
    report.metrics = _slim_metrics(metrics)
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
        for k in (f"design__{metric}__count__corner:nom_tt_025C_5v00",):
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
    }.items() if v is not None}
