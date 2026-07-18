"""RTL simulation runner (iverilog + vvp).

Ports GarudaChip's ``backend/garuda_api/sim.py`` run logic into Chip Orchestra's
stage-oriented model: compile every source with ``iverilog -g2012``, run the
resulting image with ``vvp``, capture the combined log, detect the ``design.vcd``
waveform and (best-effort) parse a compact waveform summary.

All subprocess calls go through an injected :class:`CommandRunner` so tests can
run without iverilog/vvp installed.
"""
from __future__ import annotations

import json
import os
import re
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
    ``exports/sim.vvp``; simulation runs with the WORKSPACE ROOT as CWD so the
    design-root-relative paths the RTL uses actually resolve —
    ``$readmemh("rtl/weights.mem")`` and testbench dumps like
    ``$writememh("waves/chip_output.mem")``. (Running from ``waves/`` broke
    every ``rtl/*.mem`` load: the weights read as X and the self-check failed
    on garbage outputs.) A bare ``$dumpfile("design.vcd")`` lands at the root
    and is moved into ``waves/`` afterwards.
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

    # ONE testbench per simulation: the flow also writes per-IP UNIT testbenches
    # (tb/<module>_tb.v) for generation-time verify — compiling them all together
    # runs every tb simultaneously and any unit tb's $fatal kills the MAIN run.
    # Keep only the TOP testbench: <top>_tb.* when present, else the tb that
    # instantiates the top module, else the largest tb.
    tbs = [p for p in vfiles if "tb" in p.parts or p.stem.endswith("_tb")]
    if len(tbs) > 1:
        chosen = next((p for p in tbs if top and p.stem == f"{top}_tb"), None)
        if chosen is None and top:
            for p in tbs:
                try:
                    if re.search(rf"\b{re.escape(top)}\s+(#\s*\(|\w+\s*\()", p.read_text(errors="replace")):
                        chosen = p
                        break
                except OSError:
                    continue
        if chosen is None:
            chosen = max(tbs, key=lambda p: p.stat().st_size if p.exists() else 0)
        dropped = [p.name for p in tbs if p != chosen]
        vfiles = [p for p in vfiles if p not in tbs or p == chosen]
        report.warnings.append(
            f"multiple testbenches found; simulating {chosen.name} (unit tbs excluded: {', '.join(dropped)})")

    vvp_path = exports_dir / "sim.vvp"
    vcd_path = waves_dir / "design.vcd"
    # Stale outputs must never masquerade as this run's results: the chip
    # output dump (and its render) belongs to THE RUN THAT PRODUCED IT — an old
    # chip_output.mem once showed up (and compared) as if the new tb had
    # written it. golden_output.* stays: TB_GEN produces it, not the sim.
    for stale in (vvp_path, vcd_path, workspace / "design.vcd",
                  waves_dir / "chip_output.mem", waves_dir / "chip_output.png"):
        if stale.exists():
            stale.unlink()

    # The elaboration ROOT must be the TESTBENCH, never the DUT: `-s <dut>`
    # elaborated the bare design with dangling inputs, vvp ran NOTHING, printed
    # nothing, and the silent run slipped through as a pass.
    tb_files = [p for p in vfiles if "tb" in p.parts or p.stem.endswith("_tb")]
    sim_root = tb_files[0].stem if tb_files else top

    log: List[str] = []
    inc = f"-I{rtl_dir}"
    compile_cmd = [_iverilog_bin(), "-g2012", "-o", str(vvp_path), inc]
    if sim_root:
        compile_cmd += ["-s", sim_root]
    compile_cmd += [str(p) for p in vfiles]
    log.append("$ " + " ".join(
        ["iverilog", "-g2012", "-o", "exports/sim.vvp", "-I rtl"]
        + (["-s", sim_root] if sim_root else [])
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
    run_res = runner.run([_vvp_bin(), str(vvp_path)], cwd=workspace, timeout=timeout)
    # A tb that dumps a bare "design.vcd" writes it at the workspace root now —
    # move it to the standard waves/ location.
    root_vcd = workspace / "design.vcd"
    if root_vcd.is_file() and not vcd_path.is_file():
        root_vcd.replace(vcd_path)
    passed = None
    if run_res.not_found:
        log.append("vvp is not installed / not on PATH.")
        report.warnings.append("vvp not available; compiled but not executed")
    elif run_res.timed_out:
        log.append("(simulation timed out — check for a missing $finish)")
        report.warnings.append("simulation timeout")
        passed = False
    else:
        if run_res.stdout.strip():
            log.append(run_res.stdout.strip())
        if run_res.stderr.strip():
            log.append("[stderr] " + run_res.stderr.strip())
        # The self-checking testbench's VERDICT — this is what makes the SIM
        # stage honest instead of "it ran, therefore success".
        out_text = run_res.stdout + "\n" + run_res.stderr
        import re as _re
        if _re.search(r"FAILED|\$fatal|ERROR:|mismatch|assert(ion)?\s+fail", out_text, _re.I):
            passed = False
        elif _re.search(r"TEST\s+PASSED|ALL\s+TESTS?\s+PASSED", out_text, _re.I):
            passed = True
        elif tb_files:
            # A testbench that ran but printed NO verdict proves nothing —
            # silence is not success (a silent run is how the fake pass
            # happened). Treated as a failure so the repair loop engages.
            passed = False
            log.append("(testbench printed no TEST PASSED/FAILED verdict — treated as FAILED; "
                       "a self-checking tb must $display its verdict)")

    if vcd_path.is_file():
        report.waveform = True
        try:
            wave_json = vcd.to_wave_json(vcd_path.read_text(errors="replace"))
            # The full trace data is BIG (blew the 64KB report_json DB column) —
            # persist it as a workspace file and keep only a compact summary in
            # the report itself.
            wave_json_path = waves_dir / "waveform.json"
            wave_json_path.write_text(json.dumps(wave_json))
            register_artifact(artifacts, path="waves/waveform.json", kind="waveform", stage="SIM", base=workspace)
            report.waveform_summary = {
                "tmax": wave_json.get("tmax", 0),
                "signals": [{"name": s.get("name"), "width": s.get("width")}
                            for s in wave_json.get("signals", [])][:32],
                "trace_path": "waves/waveform.json",
            }
        except Exception as exc:  # noqa: BLE001 - waveform parse must never fail the stage
            log.append(f"(waveform parse failed: {exc})")
            report.warnings.append(f"waveform parse failed: {exc}")
        register_artifact(artifacts, path="waves/design.vcd", kind="waveform", stage="SIM", base=workspace)
        # Render the waveform to a PNG so the UI can SHOW the signals toggling
        # (GarudaChip show_waveform); best-effort, never fails the stage.
        if vcd.render_png(vcd_path, waves_dir / "waveform.png"):
            log.append("rendered waves/waveform.png")
            register_artifact(artifacts, path="waves/waveform.png", kind="image", stage="SIM", base=workspace)

    # CHIP OUTPUT rendering (GarudaChip inference display): a testbench that
    # $writememh-dumps the chip's RESULT into waves/*.mem gets that data
    # rendered to a PNG so the UI shows what the RTL actually computed.
    from .memimg import render_mem_image, _read_values
    for mem_file in sorted(waves_dir.glob("*.mem")):
        out_png = mem_file.with_suffix(".png")
        if render_mem_image(mem_file, out_png, workspace=workspace):
            rel = f"waves/{out_png.name}"
            log.append(f"rendered chip data {rel} from {mem_file.name}")
            register_artifact(artifacts, path=rel, kind="image", stage="SIM", base=workspace)

    # GOLDEN COMPARISON (python-first verification): the chip is only correct
    # when input → RTL output equals input → golden-model output. Deterministic
    # value-by-value check; any mismatch fails the stage with the diff.
    golden_mem = waves_dir / "golden_output.mem"
    chip_mem = waves_dir / "chip_output.mem"
    golden_match = None
    # GOLDEN INDEPENDENCE gate: a testbench that $writememh-writes the golden
    # file is comparing the chip against its own fabrication — reject it.
    tb_dir = workspace / "tb"
    if tb_dir.is_dir():
        for tb_file in sorted(tb_dir.glob("*.*v")):
            try:
                tb_txt = tb_file.read_text(errors="replace")
            except Exception:  # noqa: BLE001
                continue
            if re.search(r"\$writememh\s*\(\s*\"[^\"]*golden", tb_txt):
                passed = False
                log.append(f"CONTRACT VIOLATION: {tb_file.name} writes waves/golden_output.mem — "
                           "the desired output must come from the Python golden model, never the "
                           "testbench; remove that dump and regenerate the golden with run_python")
                report.errors.append("testbench fabricates golden_output.mem")
                break
    if golden_mem.is_file() and chip_mem.is_file():
        golden_vals = _read_values(golden_mem)
        chip_vals = _read_values(chip_mem)
        diffs = []
        if len(golden_vals) != len(chip_vals):
            diffs.append(f"length mismatch: golden={len(golden_vals)} chip={len(chip_vals)}")
        for i, (gv, cv) in enumerate(zip(golden_vals, chip_vals)):
            if gv != cv:
                diffs.append(f"index {i}: golden=0x{gv:x} chip=0x{cv:x}")
            if len(diffs) >= 12:
                diffs.append("… (more mismatches truncated)")
                break
        if diffs:
            passed = False
            log.append("GOLDEN MISMATCH — chip output differs from the golden model:")
            log.extend("  " + d for d in diffs)
            report.errors.append(f"chip output != golden output ({len(diffs)} diff(s) shown)")
        else:
            log.append(f"✓ chip output MATCHES the golden model ({len(golden_vals)} values)")
        golden_match = not diffs
    else:
        log.append(
            'no design.vcd produced - add `$dumpfile("design.vcd"); '
            '$dumpvars(0, <tb>);` to your testbench to see a waveform.'
        )
        report.warnings.append("no waveform (design.vcd) produced")

    verdict = ("— testbench PASSED" if passed is True
               else "— testbench FAILED (see the log)" if passed is False
               else "(no explicit TEST PASSED/FAILED verdict printed)")
    report.summary = (
        f"Simulation completed {verdict}" if report.compiled else "Simulation failed"
    ) + (" with waveform." if report.waveform else ".")
    if passed is False:
        report.errors.append("self-checking testbench FAILED")
    report.metrics = {
        "compiled": report.compiled,
        "waveform": report.waveform,
        "passed": passed,
        "golden_match": golden_match,
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
