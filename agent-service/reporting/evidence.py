"""Evidence collection from the task workspace and EDA stage reports.

Adapted from GarudaChip's ``report_agent.py`` evidence model: instead of
hallucinating a summary, we scan the produced artifacts (RTL, testbenches,
waveforms, GDS) and parse the structured EDA stage reports, then normalize
everything into a single :class:`ReportContext` the markdown renderer consumes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from context import files as wsfiles


@dataclass
class ReportContext:
    task_id: str = ""
    task_name: str = ""
    design_brief: str = ""
    top_module: str = ""
    rtl_files: List[str] = field(default_factory=list)
    tb_files: List[str] = field(default_factory=list)
    wave_files: List[str] = field(default_factory=list)
    gds_files: List[str] = field(default_factory=list)
    report_files: List[str] = field(default_factory=list)
    reference_files: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    signoff: Dict[str, Any] = field(default_factory=dict)
    tapeout_ready: bool = False
    simulation: Dict[str, Any] = field(default_factory=dict)
    stage_reports: Dict[str, Any] = field(default_factory=dict)
    architecture_notes: str = ""
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    # GOLDEN_GEN's manifest (golden/golden_summary.json): the human-approved
    # Python reference model's IP decomposition, test results and vectors.
    golden: Dict[str, Any] = field(default_factory=dict)
    golden_files: List[str] = field(default_factory=list)
    # Measured cycle budget: clock edges actually counted in the simulation
    # waveform, plus the derived throughput. Empty when no VCD was produced.
    timing_profile: Dict[str, Any] = field(default_factory=dict)
    # Ordered module chain the data traverses (top -> sub-toplevel -> leaf IPs),
    # rendered as the report's dataflow description.
    dataflow: List[Dict[str, str]] = field(default_factory=list)
    # golden/module_math.json: per-module purpose + governing equations (LaTeX
    # bodies) authored by the agent that wrote the golden model.
    module_math: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)


def _rel(workspace: Path, paths: List[Path]) -> List[str]:
    return [str(p.relative_to(workspace)) for p in paths if p.is_file()]


_TIMESCALE_UNITS = {"s": 1e9, "ms": 1e6, "us": 1e3, "ns": 1.0, "ps": 1e-3, "fs": 1e-6}


def _vcd_timing(vcd: Path) -> Dict[str, Any]:
    """Count the clock cycles the simulation actually ran.

    "How many cycles does the chip need?" is the first question asked of an
    accelerator, and nothing in the flow recorded it — the VCD is the only
    artifact that knows. Counts rising edges on the clock net rather than
    dividing the end time by a period, so a testbench that gates or stalls the
    clock still reports the truth. Best-effort: returns {} on any surprise, as
    the report must never fail over a missing waveform.
    """
    import re

    # Streamed in two passes, never fully materialized: these waveforms reach
    # tens of MB, and splitting the value-change body into a token list cost
    # far more memory than the whole report is worth.
    scale_ns = 1.0
    clk_id = ""
    best = 99
    header: List[str] = []
    try:
        with vcd.open("r", errors="replace") as fh:
            for line in fh:
                header.append(line)
                if "$enddefinitions" in line:
                    break
            head = "".join(header)
            m = re.search(r"\$timescale\s+(\d+)\s*([munpf]?s)\s*\$end", head)
            if m:
                scale_ns = int(m.group(1)) * _TIMESCALE_UNITS.get(m.group(2), 1.0)
            # Pick the clock net: exact "clk"/"clock" outranks a derived net
            # such as "clk_en" or "clk_div", which would count the wrong edges.
            for var in re.finditer(r"\$var\s+\w+\s+1\s+(\S+)\s+([^$]+?)\s*\$end", head):
                name = var.group(2).strip().split("[")[0].strip().lstrip("\\").lower()
                rank = 0 if name in ("clk", "clock") else \
                    1 if name.startswith(("clk", "clock")) else 9
                if rank < best:
                    best, clk_id = rank, var.group(1)
            if not clk_id:
                return {}

            rise = "1" + clk_id
            fall = "0" + clk_id
            cycles = 0
            last = None
            end_time = 0
            for line in fh:
                tok = line.strip()
                if not tok:
                    continue
                if tok[0] == "#":
                    try:
                        end_time = int(tok[1:])
                    except ValueError:
                        pass
                elif tok == rise:
                    if last == "0":
                        cycles += 1
                    last = "1"
                elif tok == fall:
                    last = "0"
    except OSError:
        return {}

    profile: Dict[str, Any] = {
        "clock_cycles": cycles,
        "sim_time_ns": round(end_time * scale_ns, 3),
    }
    if cycles:
        profile["ns_per_cycle"] = round(end_time * scale_ns / cycles, 3)
    return profile


def _dataflow_chain(golden: Dict[str, Any], top: str) -> List[Dict[str, str]]:
    """Order the IP blocks the data passes through, top-down, from the approved
    golden manifest — the same decomposition the RTL was generated against."""
    ips = [ip for ip in (golden.get("ips") or []) if isinstance(ip, dict) and ip.get("name")]
    if not ips:
        return []
    order = {"top": 0, "subtop": 1}
    ips.sort(key=lambda ip: order.get(str(ip.get("tier", "")).lower(), 2))
    chain = [{"name": str(ip["name"]), "tier": str(ip.get("tier", "ip")),
              "role": str(ip.get("role", "") or "")} for ip in ips]
    if top and not any(c["name"] == top for c in chain):
        chain.insert(0, {"name": top, "tier": "top", "role": "Top-level integration"})
    return chain


def collect_evidence(
    task_id: str,
    workspace: Path,
    context: Optional[Dict[str, Any]] = None,
    eda_reports: Optional[List[str]] = None,
    reference_files: Optional[List[str]] = None,
) -> ReportContext:
    context = context or {}
    workspace = Path(workspace)
    ctx = ReportContext(
        task_id=task_id,
        task_name=str(context.get("task_name", task_id)),
        design_brief=str(context.get("design_brief", context.get("spec", ""))),
        top_module=str(context.get("top_module") or context.get("top") or ""),
        reference_files=list(reference_files or context.get("reference_files", []) or []),
    )

    rtl_dir = workspace / "rtl"
    tb_dir = workspace / "tb"
    waves_dir = workspace / "waves"
    gds_dir = workspace / "gds"
    reports_dir = workspace / "reports"

    ctx.rtl_files = _rel(workspace, sorted(rtl_dir.glob("*"))) if rtl_dir.is_dir() else []
    ctx.tb_files = _rel(workspace, sorted(tb_dir.glob("*"))) if tb_dir.is_dir() else []
    ctx.wave_files = _rel(workspace, sorted(waves_dir.glob("*"))) if waves_dir.is_dir() else []
    ctx.gds_files = _rel(workspace, sorted(gds_dir.glob("*"))) if gds_dir.is_dir() else []
    ctx.report_files = _rel(workspace, sorted(reports_dir.glob("*"))) if reports_dir.is_dir() else []

    if not ctx.top_module:
        # Structural detection (the module that instantiates the others) —
        # taking the first sorted rtl file crowned a WEIGHTS file (.mem) as
        # "top module actor_b1" in the final report.
        try:
            from verilog_check import pick_top
            ctx.top_module = pick_top(rtl_dir) or ""
        except Exception:  # noqa: BLE001
            pass
    if not ctx.top_module and ctx.rtl_files:
        hdl = [f for f in ctx.rtl_files if f.endswith((".v", ".sv"))]
        ctx.top_module = Path(hdl[0] if hdl else ctx.rtl_files[0]).stem

    # Load structured EDA stage reports (explicit list first, then any *_report.json).
    candidate_reports: List[str] = list(eda_reports or [])
    if reports_dir.is_dir():
        for p in sorted(reports_dir.glob("*_report.json")):
            rel = str(p.relative_to(workspace))
            if rel not in candidate_reports:
                candidate_reports.append(rel)

    for rel in candidate_reports:
        try:
            data = json.loads(wsfiles.read_file(workspace, rel))
        except (FileNotFoundError, json.JSONDecodeError, wsfiles.UnsafePathError):
            continue
        stage = str(data.get("stage", Path(rel).stem)).upper()
        ctx.stage_reports[stage] = data
        if data.get("metrics"):
            ctx.metrics.update({k: v for k, v in data["metrics"].items() if v is not None})
        if data.get("signoff"):
            ctx.signoff = data["signoff"]
        if data.get("tapeout_ready"):
            ctx.tapeout_ready = bool(data["tapeout_ready"])
        if stage == "SIM" or data.get("waveform") is not None:
            ctx.simulation = {
                "compiled": data.get("compiled"),
                "waveform": data.get("waveform"),
                "summary": data.get("summary", ""),
            }
        for artifact in data.get("artifacts", []) or []:
            if artifact not in ctx.artifacts:
                ctx.artifacts.append(artifact)

    arch_note = reports_dir / "rtl_architecture.md"
    if arch_note.is_file():
        ctx.architecture_notes = arch_note.read_text(errors="replace")

    # The golden reference model: the specification the RTL was measured
    # against, approved by a human before generation started.
    golden_dir = workspace / "golden"
    if golden_dir.is_dir():
        ctx.golden_files = _rel(workspace, sorted(golden_dir.rglob("*")))
        try:
            ctx.golden = json.loads(
                (golden_dir / "golden_summary.json").read_text(errors="replace"))
        except (OSError, json.JSONDecodeError):
            ctx.golden = {}
        if not isinstance(ctx.golden, dict):
            ctx.golden = {}
        try:
            math_doc = json.loads((golden_dir / "module_math.json").read_text(errors="replace"))
            ctx.module_math = math_doc if isinstance(math_doc, dict) else {}
        except (OSError, json.JSONDecodeError):
            ctx.module_math = {}

    # Cycle budget, measured from the waveform the self-checking testbench
    # produced. Prefer the RTL run; fall back to any VCD in waves/.
    for candidate in ("design.vcd", "sim.vcd", "dump.vcd"):
        vcd = waves_dir / candidate
        if vcd.is_file():
            ctx.timing_profile = _vcd_timing(vcd)
            break
    else:
        vcds = sorted(waves_dir.glob("*.vcd")) if waves_dir.is_dir() else []
        if vcds:
            ctx.timing_profile = _vcd_timing(vcds[0])

    # Derive the achievable sample rate from the CLOSED clock period, not the
    # simulation's: the simulation clock is arbitrary, the PNR one is real.
    period = ctx.metrics.get("clock_period_ns")
    cycles = ctx.timing_profile.get("clock_cycles")
    if cycles and isinstance(period, (int, float)) and period > 0:
        ctx.timing_profile["latency_us_at_clock"] = round(cycles * float(period) / 1000.0, 3)
        ctx.timing_profile["throughput_per_s"] = round(1e9 / (cycles * float(period)), 1)

    ctx.dataflow = _dataflow_chain(ctx.golden, ctx.top_module)

    return ctx
