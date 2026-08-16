"""Gate-level simulation (iverilog + vvp on the synthesized netlist).

Compiles the post-synthesis/P&R gate-level netlist together with the PDK
standard-cell behavioural Verilog models and the existing testbench, runs it,
and reports pass/fail + waveform capture. Discovers the netlist from the
LibreLane hardening run and the cell models from ``$PDK_ROOT``. Degrades
gracefully (skips, not fails) when the netlist, cell models or iverilog are
unavailable so mock/local runs still complete.
"""
from __future__ import annotations

import glob
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from runner import CommandRunner, default_runner

from .artifacts import register_artifact
from .reports import GlSimReport
from . import harden_runner as hr
from . import vcd

_PASS_RE = re.compile(r"TEST\s+PASSED|ALL\s+TESTS?\s+PASSED|PASS", re.IGNORECASE)
_FAIL_RE = re.compile(r"\$?fatal|\$?error|TEST\s+FAILED|mismatch|ERROR:", re.IGNORECASE)


def _iverilog() -> str:
    return os.getenv("IVERILOG_PATH") or os.getenv("IVERILOG_BIN", "iverilog")


def _vvp() -> str:
    return os.getenv("VVP_PATH") or os.getenv("VVP_BIN", "vvp")


def _gl_timeout() -> int:
    try:
        return int(os.getenv("EDA_JOB_TIMEOUT_GL_SIM", "900"))
    except ValueError:
        return 900


def _find_netlist(chip: Path) -> Optional[str]:
    if not chip.exists():
        return None
    for pat in ("*.nl.v", "*.pnl.v"):
        hits = sorted(glob.glob(str(chip / "runs" / "**" / pat), recursive=True))
        if hits:
            return hits[-1]
    return None


_CELL_LIB_RE = re.compile(r"\b([a-z0-9]+_fd_sc_[a-z0-9]+)__", re.I)


def _find_cell_models(netlist: str = "") -> List[str]:
    """Behavioural models for the cells the NETLIST actually instantiates.

    Handing iverilog every library under libs.ref/ ships two standard-cell
    families at once (mcu7t5v0 AND mcu9t5v0), whose primitives.v files declare
    the same modules — elaboration then failed with "Unknown module type" for
    cells that were, in fact, defined. Pick the one library the netlist names."""
    root = hr._pdk_root()
    pdk = hr._pdk()
    patterns = [
        os.path.join(root, pdk, "libs.ref", "*", "verilog", "*.v"),
        os.path.join(root, "**", "cells", "**", "*.v"),
        os.path.join(root, "**", "*sc*", "verilog", "*.v"),
    ]
    hits: List[str] = []
    for pat in patterns:
        hits = sorted(glob.glob(pat, recursive=True))
        if hits:
            break
    if not hits:
        return []
    used = ""
    try:
        if netlist:
            m = _CELL_LIB_RE.search(Path(netlist).read_text(errors="replace"))
            used = m.group(1) if m else ""
    except OSError:
        used = ""
    if not used:
        return hits
    # Keep the matching standard-cell library plus any non-standard-cell model
    # (IO pads, SRAM macros) the design may also instantiate.
    return [h for h in hits if (used in h) or ("_fd_sc_" not in h)]


def run_gl_sim(
    workspace: Path,
    top: str = "",
    opts: Optional[Dict] = None,
    runner: CommandRunner = default_runner,
    stage: str = "GL_SIM",
) -> GlSimReport:
    opts = opts or {}
    workspace = Path(workspace)
    rtl_dir = workspace / "rtl"
    tb_dir = workspace / "tb"
    waves_dir = workspace / "waves"
    logs_dir = workspace / "logs"
    for d in (waves_dir, logs_dir):
        d.mkdir(parents=True, exist_ok=True)

    report = GlSimReport(stage=stage)
    top = top or hr.pick_top(rtl_dir)
    report.top = top
    artifacts: List[dict] = []
    lines: List[str] = []

    chip = workspace / "exports" / "harden" / "chip"
    netlist = _find_netlist(chip)
    tbs = sorted(glob.glob(str(tb_dir / "*.sv")) + glob.glob(str(tb_dir / "*.v")))
    # ONLY the chip-level testbench. Compiling every tb in tb/ drags the per-IP
    # unit benches in too: they `include "params.vh"` (unresolvable from the
    # workspace root without -I rtl) and each declares its own root, so the
    # elaboration failed before it ever reached the netlist.
    chip_tbs = [t for t in tbs if Path(t).stem in (f"{top}_tb", f"tb_{top}")]
    if chip_tbs:
        dropped = [Path(t).name for t in tbs if t not in chip_tbs]
        tbs = chip_tbs
        if dropped:
            lines.append(f"gate-level sim uses the CHIP testbench only "
                         f"({Path(chip_tbs[0]).name}); unit benches excluded: {', '.join(dropped)}")
    cells = _find_cell_models(netlist)

    if not netlist:
        report.summary = "Gate-level sim skipped: no synthesized netlist found."
        report.warnings.append("no netlist (run SYNTH/PNR first)")
        _write(logs_dir, ["no netlist found"], report, artifacts, workspace)
        return report
    if not tbs:
        report.summary = "Gate-level sim skipped: no testbench found."
        report.warnings.append("no testbench")
        _write(logs_dir, ["no testbench"], report, artifacts, workspace)
        return report

    out_img = waves_dir / f"gl_{top}"
    sources = [netlist, *tbs, *cells]
    # -I rtl: the testbench `include "params.vh"`, which lives in rtl/ — without
    # it the include fails and elaboration dies before reaching the netlist.
    compile_cmd = [_iverilog(), "-g2012", "-DFUNCTIONAL", "-DUNIT_DELAY=#1",
                   "-I", str(rtl_dir), "-o", str(out_img), *sources]
    lines.append("$ iverilog -g2012 -DFUNCTIONAL (netlist + cells + tb)")
    cres = runner.run(compile_cmd, cwd=workspace, timeout=_gl_timeout())
    lines += [ln.rstrip() for ln in ((cres.stdout or "") + "\n" + (cres.stderr or "")).splitlines() if ln.strip()]
    if cres.not_found:
        report.summary = "Gate-level sim could not run: iverilog not available."
        report.warnings.append("iverilog not available")
        _write(logs_dir, lines, report, artifacts, workspace)
        return report
    if cres.returncode != 0:
        report.compiled = False
        report.summary = "Gate-level netlist failed to compile."
        report.errors.append("gate-level compile failed")
        _write(logs_dir, lines, report, artifacts, workspace)
        return report
    report.compiled = True

    run_cmd = [_vvp(), str(out_img)]
    lines.append("$ vvp gl_" + top)
    rres = runner.run(run_cmd, cwd=workspace, timeout=_gl_timeout())
    sim_out = (rres.stdout or "") + ("\n" + rres.stderr if rres.stderr else "")
    lines += [ln.rstrip() for ln in sim_out.splitlines() if ln.strip()]

    report.passed = bool(_PASS_RE.search(sim_out)) and not bool(_FAIL_RE.search(sim_out))
    gl_vcd = workspace / "design.vcd"
    dest_vcd = waves_dir / f"gl_{top}.vcd"
    if gl_vcd.is_file():
        gl_vcd.replace(dest_vcd)
    if dest_vcd.is_file():
        report.waveform = True
        report.netlist = os.path.relpath(netlist, workspace)
        register_artifact(artifacts, path=f"waves/gl_{top}.vcd", kind="waveform", stage=stage, base=workspace)
        # Same guard as SIM: read_text() on a multi-GB dump is what OOM-killed
        # the whole eda-service mid-stage. A gate-level trace is BIGGER than the
        # RTL one (every cell instance is a scope), so this path is the more
        # likely of the two to blow up. The verdict comes from stdout, not the
        # waveform, so skipping the parse costs only the metrics.
        from .sim_runner import _vcd_too_big
        oversized = _vcd_too_big(dest_vcd.stat().st_size)
        if oversized:
            lines.append(oversized)
            report.warnings.append(oversized)
        else:
            try:
                wave = vcd.to_wave_json(dest_vcd.read_text(errors="replace"))
                report.metrics["waveform_signals"] = len(wave.get("signals", []))
                report.metrics["waveform_tmax"] = wave.get("tmax", 0)
            except Exception:  # noqa: BLE001
                pass

    report.summary = (
        f"Gate-level sim: compiled={report.compiled}, "
        f"{'PASSED' if report.passed else 'FAILED/UNKNOWN'}"
        + (", waveform captured" if report.waveform else "") + "."
    )
    _write(logs_dir, lines, report, artifacts, workspace)
    return report


def _write(logs_dir: Path, lines: List[str], report: GlSimReport, artifacts: List[dict], workspace: Path) -> None:
    log_path = logs_dir / "gl_sim.log"
    log_path.write_text("\n".join(lines).strip() + "\n")
    register_artifact(artifacts, path="logs/gl_sim.log", kind="log", stage=report.stage, base=workspace)
    report.raw_log_paths.append("logs/gl_sim.log")
    report.artifacts = artifacts


__all__ = ["run_gl_sim"]
