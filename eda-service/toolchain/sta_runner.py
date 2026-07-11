"""Static timing + power analysis (OpenSTA).

Runs ``sta`` on the post-P&R gate-level netlist to extract worst/total negative
slack and a power breakdown (``report_power`` with switching-activity default).
Discovers the netlist/SDC/liberty from the LibreLane hardening run under
``workspace/exports/harden/chip/runs``. When ``sta`` is not installed the runner
degrades gracefully by pulling the same headline numbers from LibreLane's
``metrics.json`` so the stage still produces a useful timing/power report.

All subprocess calls go through the injected :class:`CommandRunner`.
"""
from __future__ import annotations

import glob
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from runner import CommandRunner, default_runner

from .artifacts import register_artifact
from .reports import StaReport
from . import harden_runner as hr


def _sta_bin() -> str:
    return os.getenv("STA_PATH") or os.getenv("OPENSTA_PATH") or os.getenv("STA_BIN", "sta")


def _sta_timeout() -> int:
    try:
        return int(os.getenv("EDA_JOB_TIMEOUT_STA", "900"))
    except ValueError:
        return 900


def _find(chip: Path, *patterns: str) -> Optional[str]:
    for pat in patterns:
        hits = sorted(glob.glob(str(chip / "runs" / "**" / pat), recursive=True))
        if hits:
            return hits[-1]
    return None


def _find_liberty() -> Optional[str]:
    root = hr._pdk_root()
    hits = sorted(glob.glob(os.path.join(root, "**", "*typical*.lib"), recursive=True)) \
        or sorted(glob.glob(os.path.join(root, "**", "*.lib"), recursive=True))
    return hits[0] if hits else None


def _load_metrics(chip: Path) -> dict:
    for mp in glob.glob(str(chip / "runs" / "**" / "metrics.json"), recursive=True):
        try:
            return json.load(open(mp))
        except Exception:  # noqa: BLE001
            pass
    return {}


def _parse_float(text: str, pattern: str) -> Optional[float]:
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except (ValueError, IndexError):
        return None


def run_sta(
    workspace: Path,
    top: str = "",
    clock_period: float = 10.0,
    opts: Optional[Dict] = None,
    runner: CommandRunner = default_runner,
    stage: str = "STA",
) -> StaReport:
    opts = opts or {}
    workspace = Path(workspace)
    rtl_dir = workspace / "rtl"
    reports_dir = workspace / "reports"
    logs_dir = workspace / "logs"
    for d in (reports_dir, logs_dir):
        d.mkdir(parents=True, exist_ok=True)

    report = StaReport(stage=stage)
    artifacts: List[dict] = []
    top = top or hr.pick_top(rtl_dir)
    report.top = top

    chip = workspace / "exports" / "harden" / "chip"
    metrics = _load_metrics(chip)
    netlist = _find(chip, "*.nl.v", "*.pnl.v", "*.v") if chip.exists() else None
    sdc = _find(chip, "*.sdc") if chip.exists() else None
    liberty = _find_liberty()

    lines: List[str] = []
    used_sta = False
    if netlist and liberty:
        tcl = reports_dir / "sta.tcl"
        power_activity = float(opts.get("activity_factor", 0.1) or 0.1)
        tcl.write_text(
            f"read_liberty {liberty}\n"
            f"read_verilog {netlist}\n"
            f"link_design {top}\n"
            + (f"read_sdc {sdc}\n" if sdc else
               f"create_clock -name clk -period {clock_period} [all_inputs]\n")
            + "report_checks -path_delay min_max > /dev/stdout\n"
            "report_wns\n"
            "report_tns\n"
            f"set_power_activity -input -activity {power_activity}\n"
            "report_power\n"
            "exit\n"
        )
        cmd = [_sta_bin(), "-exit", str(tcl)]
        result = runner.run(cmd, cwd=reports_dir, timeout=_sta_timeout())
        lines.append("$ " + " ".join(["sta", "-exit", "sta.tcl"]))
        combined = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        lines += [ln.rstrip() for ln in combined.splitlines() if ln.strip()]
        if result.not_found:
            lines.append("sta not on PATH; falling back to LibreLane metrics")
        elif result.timed_out:
            lines.append(f"(sta timed out after {_sta_timeout()}s)")
            report.warnings.append("sta timeout")
        else:
            used_sta = True
            wns = _parse_float(combined, r"wns\s+(-?[0-9.]+)")
            tns = _parse_float(combined, r"tns\s+(-?[0-9.]+)")
            power = _parse_float(combined, r"Total\s+[0-9.eE+-]+\s+[0-9.eE+-]+\s+[0-9.eE+-]+\s+([0-9.eE+-]+)")
            if wns is not None:
                report.wns_ns = round(wns, 4)
            if tns is not None:
                report.tns_ns = round(tns, 4)
            if power is not None:
                report.power_mw = round(power * 1000.0, 6)
    else:
        lines.append("netlist/liberty not found; using LibreLane metrics")

    # Fallback / augmentation from LibreLane metrics.json
    if not used_sta and metrics:
        slim = hr._slim_metrics(metrics)
        if "wns_ns" in slim and isinstance(slim["wns_ns"], (int, float)):
            report.wns_ns = round(float(slim["wns_ns"]), 4)
        if "power_mw" in slim and isinstance(slim["power_mw"], (int, float)):
            report.power_mw = round(float(slim["power_mw"]) * 1000.0, 6) if slim["power_mw"] < 1 else round(float(slim["power_mw"]), 6)
        report.power_breakdown = {k: v for k, v in metrics.items() if k.startswith("power__")}

    report.timing_met = report.wns_ns >= -0.001
    report.metrics = {
        "wns_ns": report.wns_ns,
        "tns_ns": report.tns_ns,
        "power_mw": report.power_mw,
        "timing_met": report.timing_met,
        "engine": "opensta" if used_sta else "librelane-metrics",
    }
    report.summary = (
        f"STA {'(OpenSTA)' if used_sta else '(from metrics)'}: "
        f"WNS={report.wns_ns} ns, power={report.power_mw} mW, "
        f"timing {'MET' if report.timing_met else 'VIOLATED'}."
    )

    rpt = reports_dir / "sta.rpt"
    rpt.write_text("\n".join(lines).strip() + "\n" + json.dumps(report.metrics, indent=2) + "\n")
    register_artifact(artifacts, path="reports/sta.rpt", kind="report", stage=stage, base=workspace)
    report.raw_log_paths.append("reports/sta.rpt")

    power_rpt = reports_dir / "power.rpt"
    power_rpt.write_text(json.dumps({"power_mw": report.power_mw, "breakdown": report.power_breakdown}, indent=2) + "\n")
    register_artifact(artifacts, path="reports/power.rpt", kind="report", stage=stage, base=workspace)
    report.artifacts = artifacts
    return report


__all__ = ["run_sta"]
