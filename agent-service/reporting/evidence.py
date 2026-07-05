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

    def as_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)


def _rel(workspace: Path, paths: List[Path]) -> List[str]:
    return [str(p.relative_to(workspace)) for p in paths if p.is_file()]


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

    if not ctx.top_module and ctx.rtl_files:
        ctx.top_module = Path(ctx.rtl_files[0]).stem

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

    return ctx
