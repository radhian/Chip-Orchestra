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
        import gdspy

        # gdspy keeps a module-global "current library"; reset it and allow
        # duplicate cell names so multiple tests can each build a "chip_top"
        # core GDS within the same interpreter session.
        gdspy.current_library = gdspy.GdsLibrary()
        gds_dir = ws / "gds"
        gds_dir.mkdir(parents=True, exist_ok=True)
        lib = gdspy.GdsLibrary()
        cell = lib.new_cell("chip_top", overwrite_duplicate=True)
        cell.add(gdspy.Rectangle((0, 0), (200, 120), layer=22, datatype=0))
        lib.write_gds(str(gds_dir / "chip_top.gds"))
    except Exception:  # noqa: BLE001
        pass
    return ws


def test_padring_gf180_v1_produces_deliverables(tmp_path: Path, monkeypatch) -> None:
    from toolchain import padring_runner

    def fast_preview(_gds_path: Path, image_path: Path, _title: str) -> bool:
        image_path.write_bytes(b"preview")
        return True

    monkeypatch.setattr(padring_runner, "_render_gds_preview", fast_preview)
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
    import gdspy

    merged = gdspy.GdsLibrary(infile=str(ws / rep.gds))
    top_cells = merged.top_level()
    assert top_cells
    assert top_cells[0].name == "chip_top_chip"
    assert rep.metrics["assembly_core_path"].endswith("chip_top.gds")
    ring_center = (rep.metrics["assembly_ring_center_x_um"], rep.metrics["assembly_ring_center_y_um"])
    placed_core_center = (
        rep.metrics["assembly_core_center_x_um"] + rep.metrics["assembly_core_offset_x_um"],
        rep.metrics["assembly_core_center_y_um"] + rep.metrics["assembly_core_offset_y_um"],
    )
    assert placed_core_center == ring_center
    chip_top = top_cells[0]
    core_refs = [ref for ref in chip_top.references if ref.ref_cell.name == rep.metrics["assembly_core_cell"]]
    assert core_refs
    core_ref_bbox = core_refs[0].get_bounding_box()
    assert core_ref_bbox is not None
    ref_center = ((core_ref_bbox[0][0] + core_ref_bbox[1][0]) / 2, (core_ref_bbox[0][1] + core_ref_bbox[1][1]) / 2)
    assert ref_center == ring_center
    assert rep.used_real_tools is True
    assert rep.pad_summary["total_cells"] == 73
    assert rep.metrics["die_area_um2"] > 0


def test_padring_routing_adds_top_level_metal(tmp_path: Path, monkeypatch) -> None:
    """Routing is enabled by default: CHIP_TOP must carry pad-to-core metal."""
    from toolchain import padring_runner

    def fast_preview(_gds_path: Path, image_path: Path, _title: str) -> bool:
        image_path.write_bytes(b"preview")
        return True

    monkeypatch.setattr(padring_runner, "_render_gds_preview", fast_preview)
    ws = _ws(tmp_path)
    rep = run_stage(stage="PADRING", task_id="task-padring", workspace=ws,
                    opts={"top_module": "chip_top", "stage_options": {"padring": "gf180-v1"}},
                    runner=FakeRunner())
    assert isinstance(rep, PadringReport)
    assert not rep.skipped

    import gdspy

    merged = gdspy.GdsLibrary(infile=str(ws / rep.gds))
    top_cells = merged.top_level()
    assert top_cells
    chip_top = top_cells[0]
    assert chip_top.name == "chip_top_chip"

    # Routing geometry is added directly into CHIP_TOP. depth=0 excludes the
    # RING_PAD / core references (which also carry Metal2), so this returns
    # exactly the top-level routing wires.
    own_polys = chip_top.get_polygons(by_spec=True, depth=0)
    metal2 = own_polys.get((30, 0))
    assert metal2, "expected Metal2 (layer 30, datatype 0) routing geometry in CHIP_TOP"

    # The Metal2 routing must extend well beyond the small centered core, i.e.
    # the wires actually reach out toward the pads at the die edges.
    xs = [pt[0] for poly in metal2 for pt in poly]
    ys = [pt[1] for poly in metal2 for pt in poly]
    route_w = max(xs) - min(xs)
    route_h = max(ys) - min(ys)
    core_w = rep.metrics["assembly_core_width_um"]
    core_h = rep.metrics["assembly_core_height_um"]
    assert route_w > core_w or route_h > core_h

    # Metal3 power straps and routing metrics are recorded.
    assert own_polys.get((34, 0)), "expected Metal3 (layer 34, datatype 0) power straps in CHIP_TOP"
    assert rep.metrics["assembly_routes_signal"] == 4          # clk, rst_n, uart_rx, uart_tx
    assert rep.metrics["assembly_routes_power"] >= 2           # dvdd + dvss straps
    assert rep.metrics["assembly_routes_total"] >= 6


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
