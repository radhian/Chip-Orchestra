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
    try:
        import gdstk

        gds_dir = ws / "gds"
        gds_dir.mkdir(parents=True, exist_ok=True)
        lib = gdstk.Library()
        cell = lib.new_cell("chip_top")
        cell.add(gdstk.rectangle((0, 0), (200, 120), layer=22, datatype=0))
        lib.write_gds(str(gds_dir / "chip_top.gds"))
    except Exception:  # noqa: BLE001
        pass
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
    assert (ws / "padring" / "chip_top_chip_preview.png").is_file()
    assert (ws / "padring" / "chip_top_chip.svg").is_file()
    assert (ws / "padring" / "padring.log").is_file()
    assert rep.gds == "padring/chip_top_chip.gds"
    import gdstk

    merged = gdstk.read_gds(str(ws / rep.gds))
    top_cells = merged.top_level()
    assert top_cells
    assert top_cells[0].name == "chip_top_chip"
    assert rep.metrics["assembly_core_path"].endswith("chip_top.gds")
    assert rep.metrics["assembly_core_offset_x_um"] > 0
    assert rep.used_real_tools is True
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
