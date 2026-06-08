"""EDA tool wrappers: Icarus Verilog simulation and LibreLane hardening.

Both run external tools as subprocesses with timeouts and degrade gracefully if
the tool is not installed, returning a structured result rather than raising.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..config import get_settings


@dataclass
class SimResult:
    ok: bool
    output: str
    compiled: bool = False
    vcd_path: str | None = None
    tool_missing: bool = False


@dataclass
class HardenResult:
    ok: bool
    output: str
    gds_path: str | None = None
    metrics: dict = field(default_factory=dict)
    tool_missing: bool = False


def _run(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str, bool]:
    """Run a command, returning (returncode, combined_output, tool_missing)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), False
    except FileNotFoundError:
        return 127, f"Tool not found: {cmd[0]}", True
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") + (exc.stderr or "") if isinstance(exc.stdout, str) else ""
        return 124, f"{out}\n[timed out after {timeout}s]", False


def simulate(
    sim_dir: Path,
    source_files: list[Path],
    top_module: str,
) -> SimResult:
    """Compile with iverilog and run with vvp; parse self-checking TB output."""
    settings = get_settings()
    sim_dir.mkdir(parents=True, exist_ok=True)
    out_bin = sim_dir / "sim.out"

    compile_cmd = [
        settings.iverilog_bin,
        "-g2012",
        "-o",
        str(out_bin),
        "-s",
        top_module,
        *[str(p) for p in source_files],
    ]
    rc, compile_out, missing = _run(compile_cmd, sim_dir, settings.sim_timeout_sec)
    if missing:
        return SimResult(ok=False, output=compile_out, tool_missing=True)
    if rc != 0:
        return SimResult(ok=False, output=f"[iverilog compile failed]\n{compile_out}", compiled=False)

    run_cmd = [settings.vvp_bin, str(out_bin)]
    rc, run_out, missing = _run(run_cmd, sim_dir, settings.sim_timeout_sec)
    if missing:
        return SimResult(ok=False, output=run_out, compiled=True, tool_missing=True)

    text = run_out.upper()
    failed = ("FAILED" in text) or ("ERROR" in text) or rc != 0
    passed = ("PASSED" in text) or ("ALL TESTS PASSED" in text) or ("RESULT: PASS" in text)
    ok = passed and not failed

    vcd = next((str(p) for p in sim_dir.glob("*.vcd")), None)
    (sim_dir / "simulation.log").write_text(compile_out + "\n" + run_out, encoding="utf-8")
    return SimResult(ok=ok, output=run_out or compile_out, compiled=True, vcd_path=vcd)


def harden(
    design_dir: Path,
    design_name: str,
    top_module: str,
    rtl_files: list[Path],
    *,
    clock_port: str = "clk",
    clock_period_ns: float = 10.0,
    pdk: str | None = None,
    stdcell: str | None = None,
) -> HardenResult:
    """Run LibreLane (RTL -> GDSII). Best-effort; degrades if LibreLane absent."""
    settings = get_settings()
    pdk = pdk or settings.default_pdk
    stdcell = stdcell or settings.default_stdcell

    run_dir = design_dir / "harden"
    run_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "DESIGN_NAME": top_module,
        "VERILOG_FILES": [f"dir::{_relpath(p, run_dir)}" for p in rtl_files],
        "CLOCK_PORT": clock_port,
        "CLOCK_PERIOD": clock_period_ns,
        "PDK": pdk,
        "STD_CELL_LIBRARY": stdcell,
        "FP_CORE_UTIL": 45,
        "PL_TARGET_DENSITY": 0.55,
    }
    config_path = run_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    base = shlex.split(settings.librelane_cmd)
    cmd = [*base, str(config_path)]
    rc, output, missing = _run(cmd, run_dir, settings.harden_timeout_sec)
    if missing:
        return HardenResult(
            ok=False,
            output=(
                "LibreLane is not installed/!on PATH. RTL was verified but not hardened.\n"
                f"Configure LIBRELANE_CMD (current: '{settings.librelane_cmd}') to enable RTL->GDSII.\n"
                f"{output}"
            ),
            tool_missing=True,
        )

    gds = next((str(p) for p in run_dir.rglob("*.gds")), None)
    metrics = _collect_metrics(run_dir)
    ok = rc == 0 and gds is not None
    return HardenResult(ok=ok, output=output, gds_path=gds, metrics=metrics)


def _relpath(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path.resolve())


def _collect_metrics(run_dir: Path) -> dict:
    """Pull a compact metrics summary from LibreLane's run output if present."""
    metrics: dict = {}
    for name in ("metrics.json", "final/metrics.json"):
        candidate = next(run_dir.rglob(name), None)
        if candidate and candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            for key in (
                "design__instance__count",
                "design__die__area",
                "timing__setup__ws",
                "timing__hold__ws",
                "power__total",
                "design__violations",
            ):
                if key in data:
                    metrics[key] = data[key]
            break
    return metrics
