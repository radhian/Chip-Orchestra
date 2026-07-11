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


def _find_cell_models() -> List[str]:
    root = hr._pdk_root()
    pdk = hr._pdk()
    patterns = [
        os.path.join(root, pdk, "libs.ref", "*", "verilog", "*.v"),
        os.path.join(root, "**", "cells", "**", "*.v"),
        os.path.join(root, "**", "*sc*", "verilog", "*.v"),
    ]
    for pat in patterns:
        hits = sorted(glob.glob(pat, recursive=True))
        if hits:
            return hits
    return []


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
    cells = _find_cell_models()

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
    compile_cmd = [_iverilog(), "-g2012", "-DFUNCTIONAL", "-DUNIT_DELAY=#1",
                   "-o", str(out_img), *sources]
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
