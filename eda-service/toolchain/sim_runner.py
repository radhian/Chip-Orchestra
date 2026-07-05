"""RTL simulation runner (iverilog + vvp).

Ports GarudaChip's ``backend/garuda_api/sim.py`` run logic into Chip Orchestra's
stage-oriented model: compile every source with ``iverilog -g2012``, run the
resulting image with ``vvp``, capture the combined log, detect the ``design.vcd``
waveform and (best-effort) parse a compact waveform summary.

All subprocess calls go through an injected :class:`CommandRunner` so tests can
run without iverilog/vvp installed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from runner import CommandRunner, default_runner

from .artifacts import register_artifact
from .reports import LintReport, SimReport
from . import vcd

RTL_EXT = (".v", ".sv", ".vh", ".svh")
COMPILE_EXT = (".v", ".sv")


def _iverilog_bin() -> str:
    return os.getenv("IVERILOG_PATH") or os.getenv("IVERILOG_BIN", "iverilog")


def _vvp_bin() -> str:
    return os.getenv("VVP_PATH") or os.getenv("VVP_BIN", "vvp")


def _sim_timeout() -> int:
    try:
        return int(os.getenv("EDA_JOB_TIMEOUT_SIM", "120"))
    except ValueError:
        return 120


def run_simulation(
    workspace: Path,
    sources: List[Path],
    top: str,
    opts: Optional[Dict] = None,
    runner: CommandRunner = default_runner,
) -> SimReport:
    """Compile + run the given ``sources`` and return a :class:`SimReport`.

    ``workspace`` is the standardized task workspace. Compilation writes
    ``exports/sim.vvp``; simulation runs with ``waves/`` as CWD so a testbench
    ``$dumpfile("design.vcd")`` lands at ``waves/design.vcd``.
    """
    opts = opts or {}
    workspace = Path(workspace)
    rtl_dir = workspace / "rtl"
    waves_dir = workspace / "waves"
    logs_dir = workspace / "logs"
    exports_dir = workspace / "exports"
    for d in (waves_dir, logs_dir, exports_dir):
        d.mkdir(parents=True, exist_ok=True)

    report = SimReport(top=top)
    artifacts: List[dict] = []

    vfiles = [Path(p) for p in sources if Path(p).suffix.lower() in COMPILE_EXT]
    if not vfiles:
        report.summary = "No .v/.sv sources found to simulate."
        report.errors.append("no synthesizable/testbench sources present in workspace")
        return report

    vvp_path = exports_dir / "sim.vvp"
    vcd_path = waves_dir / "design.vcd"
    for stale in (vvp_path, vcd_path):
        if stale.exists():
            stale.unlink()

    log: List[str] = []
    inc = f"-I{rtl_dir}"
    compile_cmd = [_iverilog_bin(), "-g2012", "-o", str(vvp_path), inc]
    if top:
        compile_cmd += ["-s", top]
    compile_cmd += [str(p) for p in vfiles]
    log.append("$ " + " ".join(
        ["iverilog", "-g2012", "-o", "exports/sim.vvp", "-I rtl"]
        + (["-s", top] if top else [])
        + [p.name for p in vfiles]
    ))

    timeout = _sim_timeout()
    compile_res = runner.run(compile_cmd, cwd=workspace, timeout=timeout)
    if compile_res.not_found:
        log.append("iverilog is not installed / not on PATH.")
        report.errors.append("iverilog not available")
        report.summary = "Simulation could not run: iverilog not available."
        _finalize_log(report, logs_dir, log, artifacts)
        return report
    if compile_res.timed_out:
        log.append(f"(compile timed out after {timeout}s)")
        report.errors.append("compile timeout")
        report.summary = "Simulation compile timed out."
        _finalize_log(report, logs_dir, log, artifacts)
        return report

    log.append(compile_res.output or "(compiled, no warnings)")
    if compile_res.returncode != 0:
        report.compiled = False
        report.errors.append("compile failed")
        report.summary = "RTL compilation failed; fix the errors in the log."
        report.warnings.append("fix the compile errors above, then run again")
        _finalize_log(report, logs_dir, log, artifacts)
        return report

    report.compiled = True
    log.append("$ vvp exports/sim.vvp")
    run_res = runner.run([_vvp_bin(), str(vvp_path)], cwd=waves_dir, timeout=timeout)
    if run_res.not_found:
        log.append("vvp is not installed / not on PATH.")
        report.warnings.append("vvp not available; compiled but not executed")
    elif run_res.timed_out:
        log.append("(simulation timed out — check for a missing $finish)")
        report.warnings.append("simulation timeout")
    else:
        if run_res.stdout.strip():
            log.append(run_res.stdout.strip())
        if run_res.stderr.strip():
            log.append("[stderr] " + run_res.stderr.strip())

    if vcd_path.is_file():
        report.waveform = True
        try:
            report.waveform_summary = vcd.to_wave_json(vcd_path.read_text(errors="replace"))
        except Exception as exc:  # noqa: BLE001 - waveform parse must never fail the stage
            log.append(f"(waveform parse failed: {exc})")
            report.warnings.append(f"waveform parse failed: {exc}")
        register_artifact(artifacts, path="waves/design.vcd", kind="waveform", stage="SIM", base=workspace)
    else:
        log.append(
            'no design.vcd produced - add `$dumpfile("design.vcd"); '
            '$dumpvars(0, <tb>);` to your testbench to see a waveform.'
        )
        report.warnings.append("no waveform (design.vcd) produced")

    report.summary = (
        "Simulation completed" if report.compiled else "Simulation failed"
    ) + (" with waveform." if report.waveform else ".")
    report.metrics = {
        "compiled": report.compiled,
        "waveform": report.waveform,
        "signal_count": len(report.waveform_summary.get("signals", [])) if report.waveform else 0,
    }
    _finalize_log(report, logs_dir, log, artifacts)
    return report


def run_lint(
    workspace: Path,
    sources: List[Path],
    top: str = "",
    opts: Optional[Dict] = None,
    runner: CommandRunner = default_runner,
) -> LintReport:
    """Lint synthesizable RTL with ``iverilog -t null`` (syntax/elaboration check).

    Informative, not fatal: findings are captured as warnings/errors on the
    report rather than raising, mirroring GarudaChip's tolerant lint policy.
    """
    opts = opts or {}
    workspace = Path(workspace)
    rtl_dir = workspace / "rtl"
    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    report = LintReport()
    artifacts: List[dict] = []
    vfiles = [Path(p) for p in sources if Path(p).suffix.lower() in COMPILE_EXT]
    report.checked_files = [p.name for p in vfiles]
    log: List[str] = []

    if not vfiles:
        report.summary = "No RTL sources to lint."
        report.clean = True
        _finalize_lint_log(report, logs_dir, log, artifacts)
        return report

    inc = f"-I{rtl_dir}"
    cmd = [_iverilog_bin(), "-g2012", "-t", "null", inc]
    if top:
        cmd += ["-s", top]
    cmd += [str(p) for p in vfiles]
    log.append("$ " + " ".join(["iverilog", "-g2012", "-t", "null", "-I rtl"]
                                + (["-s", top] if top else []) + [p.name for p in vfiles]))
    res = runner.run(cmd, cwd=workspace, timeout=_sim_timeout())
    if res.not_found:
        log.append("iverilog is not installed / not on PATH.")
        report.warnings.append("iverilog not available; lint skipped")
        report.summary = "Lint skipped: iverilog not available."
        _finalize_lint_log(report, logs_dir, log, artifacts)
        return report

    out = res.output
    if out:
        log.append(out)
    if res.returncode != 0:
        report.clean = False
        report.errors.append("lint reported elaboration errors")
        report.summary = "Lint found issues; see log."
    else:
        report.clean = True
        report.summary = "Lint clean."
    # surface warning lines
    for line in out.splitlines():
        if "warning" in line.lower():
            report.warnings.append(line.strip())
    report.metrics = {
        "checked_files": len(vfiles),
        "clean": report.clean,
        "warning_count": len(report.warnings),
    }
    _finalize_lint_log(report, logs_dir, log, artifacts)
    return report


def _finalize_lint_log(report: LintReport, logs_dir: Path, log: List[str], artifacts: List[dict]) -> None:
    log_path = logs_dir / "lint.log"
    log_path.write_text("\n".join(l for l in log if l).strip() + "\n")
    register_artifact(artifacts, path="logs/lint.log", kind="log", stage="LINT", base=logs_dir.parent)
    report.raw_log_paths.append("logs/lint.log")
    report.artifacts = artifacts


def _finalize_log(report: SimReport, logs_dir: Path, log: List[str], artifacts: List[dict]) -> None:
    log_path = logs_dir / "sim.log"
    log_path.write_text("\n".join(l for l in log if l).strip() + "\n")
    workspace = logs_dir.parent
    register_artifact(artifacts, path="logs/sim.log", kind="log", stage="SIM", base=workspace)
    report.raw_log_paths.append("logs/sim.log")
    report.artifacts = artifacts
