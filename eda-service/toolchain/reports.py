"""Stage-specific structured report dataclasses.

Each EDA stage produces one of these instead of a single generic blob. They all
share a common shape (``summary``, ``metrics``, ``artifacts``, ``warnings``,
``errors``, ``raw_log_paths``) so the orchestrator and frontend can treat them
uniformly, while stage-specific fields (``compiled``/``waveform`` for sim,
``signoff``/``tapeout_ready`` for physical stages) carry the extra detail.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class BaseReport:
    stage: str = ""
    summary: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    raw_log_paths: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SimReport(BaseReport):
    stage: str = "SIM"
    top: str = ""
    compiled: bool = False
    waveform: bool = False
    waveform_summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LintReport(BaseReport):
    stage: str = "LINT"
    clean: bool = True
    checked_files: List[str] = field(default_factory=list)


@dataclass
class SynthReport(BaseReport):
    stage: str = "SYNTH"
    top: str = ""
    gds: str = ""
    png: str = ""
    signoff: Dict[str, Any] = field(default_factory=dict)
    tapeout_ready: bool = False


@dataclass
class PnrReport(BaseReport):
    stage: str = "PNR"
    top: str = ""
    gds: str = ""
    png: str = ""
    signoff: Dict[str, Any] = field(default_factory=dict)
    tapeout_ready: bool = False


@dataclass
class DrcLvsReport(BaseReport):
    stage: str = "DRC_LVS"
    top: str = ""
    gds: str = ""
    png: str = ""
    signoff: Dict[str, Any] = field(default_factory=dict)
    tapeout_ready: bool = False


@dataclass
class SignoffReport(BaseReport):
    stage: str = "SIGNOFF"
    signoff: Dict[str, Any] = field(default_factory=dict)
    tapeout_ready: bool = False


@dataclass
class StaReport(BaseReport):
    stage: str = "STA"
    top: str = ""
    wns_ns: float = 0.0
    tns_ns: float = 0.0
    power_mw: float = 0.0
    timing_met: bool = False
    power_breakdown: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GlSimReport(BaseReport):
    stage: str = "GL_SIM"
    top: str = ""
    compiled: bool = False
    passed: bool = False
    waveform: bool = False
    netlist: str = ""


@dataclass
class RenderReport(BaseReport):
    stage: str = "RENDER"
    top: str = ""
    images: List[str] = field(default_factory=list)


@dataclass
class PadringReport(BaseReport):
    stage: str = "PADRING"
    design: str = ""
    config: str = ""       # gf180-v1 / none
    cfg_file: str = ""     # resolved padring config
    def_file: str = ""     # padring DEF
    gds: str = ""          # chip-level pad-ring GDS (primary deliverable)
    lef: str = ""          # pad-ring abstract LEF
    svg: str = ""          # visual preview
    verilog: str = ""      # ring netlist
    deliverables: List[str] = field(default_factory=list)
    pad_summary: Dict[str, Any] = field(default_factory=dict)
    used_real_tools: bool = False
    skipped: bool = False


# Physical (hardening) stages share the same underlying LibreLane run shape.
HARDEN_REPORT_TYPES = {
    "SYNTH": SynthReport,
    "PNR": PnrReport,
    "DRC_LVS": DrcLvsReport,
}
