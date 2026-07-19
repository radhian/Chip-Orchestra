from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobs import run_stage
from runner import CommandResult
from toolchain.reports import PadringReport
from workspace import ensure_workspace


class FakeRunner:
    """Simulates a host with no padring/KLayout binaries installed."""

    def __init__(self, not_found: bool = True):
        self.not_found = not_found
        self.programs = []

    def run(self, args, *, cwd=None, timeout=None, env=None) -> CommandResult:
        prog = Path(str(args[0])).name
        self.programs.append(prog)
        if self.not_found:
            return CommandResult(args=list(map(str, args)), returncode=127, not_found=True)
        return CommandResult(args=list(map(str, args)), returncode=0, stdout="", stderr="")


def _ws(tmp_path: Path) -> Path:
    ws = ensure_workspace("task-padring", root=tmp_path)
    (ws / "rtl" / "chip_top.sv").write_text("module chip_top; endmodule\n")
    return ws


def test_padring_gf180_v1_produces_deliverables(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    rep = run_stage(stage="PADRING", task_id="task-padring", workspace=ws,
                    opts={"top_module": "chip_top", "stage_options": {"padring": "gf180-v1"}},
                    runner=FakeRunner())
    assert isinstance(rep, PadringReport)
    assert rep.stage == "PADRING"
    assert not rep.skipped
    # Primary + supporting deliverables exist on disk.
    for rel in (rep.gds, rep.def_file, rep.lef, rep.svg, rep.cfg_file, rep.verilog):
        assert rel
        assert (ws / rel).is_file()
    # GDS mirrored into the standard gds/ dir for downstream previews.
    assert list((ws / "gds").glob("*.gds"))
    assert rep.pad_summary["total_cells"] == 73
    assert rep.metrics["die_area_um2"] > 0


def test_padring_none_is_skipped_success(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    rep = run_stage(stage="PADRING", task_id="task-padring", workspace=ws,
                    opts={"top_module": "chip_top", "stage_options": {"padring": "none"}},
                    runner=FakeRunner())
    assert isinstance(rep, PadringReport)
    assert rep.skipped is True
    assert rep.summary
    assert not (ws / "padring").exists() or not list((ws / "padring").glob("*.gds"))


def test_padring_missing_option_is_skipped(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    rep = run_stage(stage="PADRING", task_id="task-padring", workspace=ws,
                    opts={"top_module": "chip_top"}, runner=FakeRunner())
    assert isinstance(rep, PadringReport)
    assert rep.skipped is True
