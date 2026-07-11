from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobs import run_stage
from runner import CommandResult
from toolchain.reports import GlSimReport, RenderReport, StaReport
from workspace import ensure_workspace


class FakeRunner:
    def __init__(self):
        self.programs = []

    def run(self, args, *, cwd=None, timeout=None, env=None) -> CommandResult:
        prog = Path(str(args[0])).name
        self.programs.append(prog)
        return CommandResult(args=list(map(str, args)), returncode=0, stdout="", stderr="")


def _ws(tmp_path: Path) -> Path:
    ws = ensure_workspace("task-new-stages", root=tmp_path)
    (ws / "rtl" / "top.sv").write_text("module top; endmodule\n")
    (ws / "tb" / "top_tb.sv").write_text("module top_tb; endmodule\n")
    return ws


def test_sta_stage_returns_sta_report(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    rep = run_stage(stage="STA", task_id="task-new-stages", workspace=ws,
                    opts={"top_module": "top"}, runner=FakeRunner())
    assert isinstance(rep, StaReport)
    assert rep.stage == "STA"
    assert "wns_ns" in rep.metrics


def test_gl_sim_stage_returns_gl_report(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    rep = run_stage(stage="GL_SIM", task_id="task-new-stages", workspace=ws,
                    opts={"top_module": "top"}, runner=FakeRunner())
    assert isinstance(rep, GlSimReport)
    assert rep.stage == "GL_SIM"
    # No hardening netlist present -> gracefully skipped, not crashed.
    assert rep.summary


def test_render_stage_returns_render_report(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    rep = run_stage(stage="RENDER", task_id="task-new-stages", workspace=ws,
                    opts={"top_module": "top"}, runner=FakeRunner())
    assert isinstance(rep, RenderReport)
    assert rep.stage == "RENDER"
    assert isinstance(rep.images, list)
