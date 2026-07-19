"""GF180MCU pad-ring assembly stage.

Runs during the *signoff* phase (after PNR) and assembles a chip-level I/O pad
ring around the hardened core, emitting the tape-out deliverable set:

* ``padring/<design>_padring.cfg`` - the resolved ``gf180-v1`` config (input)
* ``padring/<design>_padring.def`` - pad/corner/filler placement
* ``padring/<design>_padring.gds`` - chip-level GDSII (primary deliverable)
* ``padring/<design>_padring.lef`` - abstract for downstream assembly
* ``padring/<design>_padring.svg`` - visual preview
* ``padring/<design>_padring.v``   - ring netlist

Assembles the chip natively in Python with ``gdstk`` by loading the bundled
GF180MCU ``RING_PAD.gds`` and centering the hardened PNR core GDS inside it.
The historical ``padring`` binary is still attempted for supporting DEF/SVG/V
text deliverables when available, but chip-level GDS generation no longer
depends on external padring/KLayout binaries and never writes a text placeholder
for the primary GDS deliverable. Only the ``gf180-v1`` config is supported; any
other value (``none`` / unset) is a no-op success.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from runner import CommandRunner, default_runner

from .artifacts import register_artifact
from .reports import PadringReport
from . import harden_runner as hr


# ---------------------------------------------------------------------------
# gf180-v1 pad-ring definition (derived from JuanMoya/padring_gf180
# workshop_padring.cfg + the LibreLane workshop slot spec).
# ---------------------------------------------------------------------------
GF180_V1 = {
    "config_id": "gf180-v1",
    "pdk": "gf180mcuD",
    "io_library": "gf180mcu_fd_io",
    "die_um": (2935.0, 2935.0),   # 2.935 mm x 2.935 mm
    "grid_um": 0.005,
    "corner_cell": "gf180mcu_fd_io__cor",
    "filler_cells": [
        "gf180mcu_fd_io__fillnc",
        "gf180mcu_fd_io__fill1",
        "gf180mcu_fd_io__fill5",
        "gf180mcu_fd_io__fill10",
    ],
    # GF180MCU RING_PAD (openfasoc-tapeouts/gf180mcu_padframe/RING_PAD.gds)
    # Pin assignment v1 — approved 2026-07-19
    # Note: bi_t (bidirectional) pads only available on West side in this padframe.
    # UART signals bound to West; clk/rst_n on South (in_c digital input pads).
    # pad class -> (cell, count)
    "pads": {
        "analog": ("gf180mcu_fd_io__asig_5p0", 58),
        "clk": ("gf180mcu_fd_io__in_c", 1),      # clk: South
        "rst_n": ("gf180mcu_fd_io__in_c", 1),    # rst_n: South
        "uart_rx": ("gf180mcu_fd_io__bi_t", 1),  # uart_rx: West
        "uart_tx": ("gf180mcu_fd_io__bi_t", 1),  # uart_tx: West
        "dvdd": ("gf180mcu_fd_io__dvdd", 3),     # VDD: North x3
        "dvss": ("gf180mcu_fd_io__dvss", 4),     # VSS: N/E/S/W distributed
    },
}

SUPPORTED_CONFIGS = {"gf180-v1"}


def _padring_bin() -> str:
    return os.getenv("PADRING_BIN") or os.getenv("PADRING_PATH", "padring")


def _klayout() -> str:
    return os.getenv("KLAYOUT_PATH") or os.getenv("KLAYOUT_BIN", "klayout")


def _pad_summary(cfg: Dict) -> Dict[str, int]:
    pads = cfg["pads"]
    per_class = {name: count for name, (_, count) in pads.items()}
    total_io = sum(per_class.values())
    corners = 4
    return {
        **per_class,
        "corners": corners,
        "total_io": total_io,
        "total_cells": total_io + corners,
    }


def _render_cfg(cfg: Dict, design: str) -> str:
    """Reconstruct a padring-tool-style ``.cfg`` for the resolved config."""
    w, h = cfg["die_um"]
    lines: List[str] = [
        f"# Resolved pad-ring config: {cfg['config_id']}",
        f"# PDK: {cfg['pdk']}  IO library: {cfg['io_library']}",
        f"DESIGN {design};",
        f"AREA {w:g} {h:g};",
        f"GRID {cfg['grid_um']:g};",
        "",
        "# Corners",
    ]
    for i, loc in enumerate(("SE", "SW", "NE", "NW"), start=1):
        lines.append(f"CORNER CORNER_{i} {loc} {cfg['corner_cell']} ;")
    lines.append("")
    lines.append("FILLER " + " ".join(cfg["filler_cells"]) + " ;")
    lines.append("")
    lines.append("# Pads (class : cell x count)")
    for name, (cell, count) in cfg["pads"].items():
        lines.append(f"# {name}: {cell} x {count}")
    return "\n".join(lines) + "\n"


def _pad_ring_rects(cfg: Dict):
    """Distribute IO pad rectangles evenly along the four die edges.

    Returns a list of ``(x, y, w, h, cls)`` tuples in micron coordinates for
    the SVG / DEF / GDS generators. Purely geometric placement — enough for a
    representative deliverable, not a signoff-accurate placement.
    """
    W, H = cfg["die_um"]
    corner = 442.0  # padring halo (matches workshop slot core inset)
    pad_w, pad_h = 75.0, 350.0
    edge_len = max(1.0, W - 2 * corner)

    # Final NanoCGRA RING_PAD v1 assignment by edge:
    #   South: clk/rst_n use in_c digital input pads.
    #   West: UART uses bi_t pads (only available on West in this padframe).
    #   North: VDD uses three dvdd pads.
    #   VSS: dvss is distributed one pad per side.
    analog_count = cfg["pads"].get("analog", (None, 0))[1]
    edge_pads_by_side = [
        ["dvss", "clk", "rst_n"],
        ["dvss"],
        ["dvss", "dvdd", "dvdd", "dvdd"],
        ["dvss", "uart_rx", "uart_tx"],
    ]
    side_index = 0
    for _ in range(analog_count):
        edge_pads_by_side[side_index].append("analog")
        side_index = (side_index + 1) % 4

    rects = []
    idx = 0
    for edge in range(4):
        edge_pads = edge_pads_by_side[edge]
        m = len(edge_pads)
        if m == 0:
            continue
        step = edge_len / m
        for j, cls in enumerate(edge_pads):
            off = corner + step * (j + 0.5)
            if edge == 0:      # south
                x, y, pw, ph = off - pad_w / 2, 0.0, pad_w, pad_h
            elif edge == 1:    # east
                x, y, pw, ph = W - pad_h, off - pad_w / 2, pad_h, pad_w
            elif edge == 2:    # north
                x, y, pw, ph = off - pad_w / 2, H - pad_h, pad_w, pad_h
            else:              # west
                x, y, pw, ph = 0.0, off - pad_w / 2, pad_h, pad_w
            rects.append((x, y, pw, ph, cls))
            idx += 1
    return rects, corner


def _render_svg(cfg: Dict, design: str) -> str:
    W, H = cfg["die_um"]
    rects, corner = _pad_ring_rects(cfg)
    colors = {
        "analog": "#4c8bf5", "bidir": "#34a853", "dvdd": "#ea4335",
        "dvss": "#fbbc05", "clk": "#a142f4", "rst_n": "#ff6d01",
    }
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-50 -50 {W + 100:g} {H + 100:g}" '
        f'width="900" height="900">',
        f'<rect x="0" y="0" width="{W:g}" height="{H:g}" fill="#f5f5f5" stroke="#222" stroke-width="4"/>',
    ]
    cs = corner
    for cx, cy in ((0, 0), (W - cs, 0), (0, H - cs), (W - cs, H - cs)):
        parts.append(
            f'<rect x="{cx:g}" y="{cy:g}" width="{cs:g}" height="{cs:g}" '
            f'fill="#d0d0d0" stroke="#222" stroke-width="2"/>'
        )
    # core outline
    parts.append(
        f'<rect x="{cs:g}" y="{cs:g}" width="{W - 2 * cs:g}" height="{H - 2 * cs:g}" '
        f'fill="#ffffff" stroke="#888" stroke-dasharray="20,10" stroke-width="2"/>'
    )
    parts.append(
        f'<text x="{W / 2:g}" y="{H / 2:g}" font-size="120" text-anchor="middle" '
        f'fill="#666">{design}</text>'
    )
    for x, y, w, h, cls in rects:
        parts.append(
            f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" '
            f'fill="{colors.get(cls, "#4c8bf5")}" stroke="#111" stroke-width="1"/>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _render_def(cfg: Dict, design: str) -> str:
    W, H = cfg["die_um"]
    dbu = 1000  # 1000 db units / micron
    rects, _ = _pad_ring_rects(cfg)
    lines = [
        "VERSION 5.8 ;",
        'DIVIDERCHAR "/" ;',
        'BUSBITCHARS "[]" ;',
        f"DESIGN {design} ;",
        f"UNITS DISTANCE MICRONS {dbu} ;",
        f"DIEAREA ( 0 0 ) ( {int(W * dbu)} {int(H * dbu)} ) ;",
        f"COMPONENTS {len(rects) + 4} ;",
    ]
    for i, loc in enumerate(("SE", "SW", "NE", "NW"), start=1):
        lines.append(f"   - CORNER_{i} {cfg['corner_cell']} + FIXED ( 0 0 ) N ;")
    for i, (x, y, _w, _h, cls) in enumerate(rects):
        cell = cfg["pads"][cls][0]
        lines.append(f"   - {cls.upper()}_PAD_{i} {cell} + FIXED ( {int(x * dbu)} {int(y * dbu)} ) N ;")
    lines += ["END COMPONENTS", "END DESIGN", ""]
    return "\n".join(lines)


def _render_lef(cfg: Dict, design: str) -> str:
    W, H = cfg["die_um"]
    return (
        "VERSION 5.8 ;\n"
        'BUSBITCHARS "[]" ;\n'
        'DIVIDERCHAR "/" ;\n'
        f"MACRO {design}\n"
        "  CLASS BLOCK ;\n"
        "  ORIGIN 0 0 ;\n"
        f"  SIZE {W:g} BY {H:g} ;\n"
        f"END {design}\n"
        "END LIBRARY\n"
    )


def _render_verilog(cfg: Dict, design: str) -> str:
    pads = cfg["pads"]
    lines = [f"// Pad-ring netlist for {design} ({cfg['config_id']})", f"module {design} ();"]
    for name, (cell, count) in pads.items():
        for i in range(count):
            lines.append(f"  {cell} {name}_pad_{i} ();")
    for i in range(4):
        lines.append(f"  {cfg['corner_cell']} corner_{i} ();")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def _toolchain_dir() -> Path:
    return Path(__file__).resolve().parent


def _ring_pad_gds() -> Path:
    return _toolchain_dir() / "gf180" / "RING_PAD.gds"


def _find_core_gds(workspace: Path, top: str, chip_gds: Path) -> Optional[Path]:
    preferred = workspace / "gds" / f"{top}.gds"
    if preferred.is_file():
        return preferred
    candidates = sorted((workspace / "gds").glob("*.gds"))
    for candidate in candidates:
        if candidate.resolve() != chip_gds.resolve() and "padring" not in candidate.stem and "chip" not in candidate.stem:
            return candidate
    return None


def _bbox_size(bbox: Optional[Tuple[Tuple[float, float], Tuple[float, float]]]) -> Tuple[float, float]:
    if bbox is None:
        return 0.0, 0.0
    return bbox[1][0] - bbox[0][0], bbox[1][1] - bbox[0][1]


def _merge_gds(path: Path, cfg: Dict, top: str, design: str, workspace: Path) -> Dict[str, object]:
    """Merge the bundled GF180 padframe with the hardened core using gdstk."""
    import gdstk

    ring_path = _ring_pad_gds()
    if not ring_path.is_file():
        raise FileNotFoundError(f"Missing bundled padframe GDS: {ring_path}")

    ring_lib = gdstk.read_gds(str(ring_path))
    ring_tops = ring_lib.top_level()
    if not ring_tops:
        raise ValueError(f"No top-level cell found in {ring_path}")
    ring_cell = ring_tops[0]
    ring_bbox = ring_cell.bounding_box()
    ring_w, ring_h = _bbox_size(ring_bbox)
    if ring_bbox is None or ring_w <= 0 or ring_h <= 0:
        ring_w, ring_h = cfg["die_um"]
        ring_origin = (0.0, 0.0)
    else:
        ring_origin = (ring_bbox[0][0], ring_bbox[0][1])

    core_path = _find_core_gds(workspace, top, path)
    core_lib = None
    core_cell = None
    core_bbox = None
    core_offset = (0.0, 0.0)
    if core_path is not None:
        core_lib = gdstk.read_gds(str(core_path))
        core_tops = core_lib.top_level()
        if core_tops:
            core_cell = core_tops[0]
            core_bbox = core_cell.bounding_box()
            if core_bbox is not None:
                core_w, core_h = _bbox_size(core_bbox)
                core_offset = (
                    ring_origin[0] + (ring_w - core_w) / 2 - core_bbox[0][0],
                    ring_origin[1] + (ring_h - core_h) / 2 - core_bbox[0][1],
                )

    merged = gdstk.Library(unit=ring_lib.unit, precision=ring_lib.precision)
    used_names = set()
    for source_cell in ring_lib.cells:
        used_names.add(source_cell.name)
        merged.add(source_cell)
    if core_lib is not None:
        for source_cell in core_lib.cells:
            if source_cell.name in used_names:
                source_cell.name = f"CORE_{source_cell.name}"
            used_names.add(source_cell.name)
            merged.add(source_cell)

    chip = merged.new_cell(design)
    chip.add(gdstk.Reference(ring_cell))
    if core_cell is not None:
        chip.add(gdstk.Reference(core_cell, origin=core_offset))

    path.parent.mkdir(parents=True, exist_ok=True)
    merged.write_gds(str(path))
    core_w, core_h = _bbox_size(core_bbox)
    return {
        "ring_path": str(ring_path),
        "core_path": str(core_path) if core_path else "",
        "ring_width_um": round(ring_w, 3),
        "ring_height_um": round(ring_h, 3),
        "core_width_um": round(core_w, 3),
        "core_height_um": round(core_h, 3),
        "core_offset_x_um": round(core_offset[0], 3),
        "core_offset_y_um": round(core_offset[1], 3),
        "top_cell": chip.name,
        "merged_cells": len(merged.cells),
    }


def _render_gds_preview(gds_path: Path, image_path: Path, title: str) -> bool:
    """Render a KLayout-style black-background preview with legend and scale bar."""
    try:
        import gdstk
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch, Polygon as MplPolygon, Rectangle
    except Exception:  # noqa: BLE001
        return False

    layer_colors = {
        22: ("Metal1", "#3b82f6"),
        30: ("Metal2", "#22c55e"),
        34: ("Metal3", "#f59e0b"),
        36: ("Metal4", "#ef4444"),
        42: ("Metal5", "#a855f7"),
        62: ("Top metal", "#f8fafc"),
        235: ("Boundary", "#94a3b8"),
    }
    fallback_colors = ["#38bdf8", "#fb7185", "#a3e635", "#facc15", "#c084fc", "#2dd4bf"]

    lib = gdstk.read_gds(str(gds_path))
    tops = lib.top_level()
    if not tops:
        return False
    bbox = tops[0].bounding_box()
    if bbox is None:
        return False

    fig, ax = plt.subplots(figsize=(10, 10), facecolor="black")
    ax.set_facecolor("black")
    seen_layers: Dict[int, str] = {}
    polygon_count = 0
    for source_cell in [tops[0], *tops[0].dependencies(True)]:
        for poly in source_cell.polygons:
            layer = int(poly.layer)
            name, color = layer_colors.get(layer, (f"L{layer}", fallback_colors[layer % len(fallback_colors)]))
            ax.add_patch(MplPolygon(poly.points, closed=True, facecolor=color, edgecolor=color, alpha=0.78, linewidth=0.15))
            seen_layers[layer] = name
            polygon_count += 1
            if polygon_count >= 5000:
                break
        if polygon_count >= 5000:
            break
    for ref in tops[0].references:
        ref_bbox = ref.bounding_box()
        if ref_bbox is None:
            continue
        layer = 235
        name, color = layer_colors[layer]
        rxmin, rymin = ref_bbox[0]
        rxmax, rymax = ref_bbox[1]
        ax.add_patch(Rectangle((rxmin, rymin), rxmax - rxmin, rymax - rymin, fill=False, edgecolor=color, linewidth=0.8, alpha=0.95))
        seen_layers[layer] = name

    xmin, ymin = bbox[0]
    xmax, ymax = bbox[1]
    width = xmax - xmin
    height = ymax - ymin
    margin = max(width, height) * 0.04
    ax.set_xlim(xmin - margin, xmax + margin)
    ax.set_ylim(ymin - margin, ymax + margin)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title, color="white", fontsize=14, pad=12)
    ax.tick_params(colors="#cbd5e1", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#475569")

    scale_um = 500.0 if width >= 1000 else max(10.0, round(width / 5 / 10) * 10)
    sx = xmin + margin
    sy = ymin + margin
    ax.add_patch(Rectangle((sx, sy), scale_um, max(height * 0.008, 2.0), color="white"))
    ax.text(sx, sy + max(height * 0.018, 8.0), f"{scale_um:g} µm", color="white", fontsize=9, va="bottom")

    handles = [Patch(facecolor=layer_colors.get(layer, (name, fallback_colors[layer % len(fallback_colors)]))[1], label=name)
               for layer, name in sorted(seen_layers.items())[:12]]
    if handles:
        legend = ax.legend(handles=handles, loc="upper right", facecolor="#020617", edgecolor="#334155", fontsize=8)
        for text in legend.get_texts():
            text.set_color("white")

    image_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(image_path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return True


def run_padring(
    workspace: Path,
    top: str = "",
    opts: Optional[Dict] = None,
    runner: CommandRunner = default_runner,
    stage: str = "PADRING",
) -> PadringReport:
    opts = opts or {}
    workspace = Path(workspace)
    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    config_id = str(opts.get("padring") or "none").strip().lower()
    report = PadringReport(stage=stage, config=config_id)

    # No-op success when no pad ring was requested.
    if config_id not in SUPPORTED_CONFIGS:
        report.skipped = True
        report.summary = (
            f"Pad ring not requested (padring={config_id or 'none'}) — stage skipped."
        )
        report.metrics = {"skipped": True, "config": config_id or "none"}
        (logs_dir / "padring.log").write_text(report.summary + "\n")
        register_artifact(report.artifacts, path="logs/padring.log", kind="log", stage=stage, base=workspace)
        report.raw_log_paths.append("logs/padring.log")
        return report

    cfg = GF180_V1
    top = top or hr.pick_top(workspace / "rtl") or "chip_top"
    design = f"{top}_padring"

    pad_dir = workspace / "padring"
    gds_dir = workspace / "gds"
    for d in (pad_dir, gds_dir):
        d.mkdir(parents=True, exist_ok=True)

    log_lines: List[str] = [f"[padring] config={config_id} design={design} pdk={cfg['pdk']}"]
    artifacts: List[dict] = []
    deliverables: List[str] = []

    def _emit(rel: str, kind: str, summary: str = "") -> None:
        deliverables.append(rel)
        register_artifact(artifacts, path=rel, kind=kind, stage=stage, base=workspace, summary=summary)

    # 1. Resolved config (reproducible input).
    cfg_file = pad_dir / f"{design}.cfg"
    cfg_file.write_text(_render_cfg(cfg, design))
    report.cfg_file = f"padring/{cfg_file.name}"
    _emit(report.cfg_file, "config", "resolved gf180-v1 pad-ring config")

    # 2. DEF placement — try the real padring binary first, else deterministic stub.
    def_file = pad_dir / f"{design}.def"
    used_real = False
    cmd = [
        _padring_bin(), "-v",
        "--def", str(def_file),
        "--svg", str(pad_dir / f"{design}.svg"),
        "--ver", str(pad_dir / f"{design}.v"),
        str(cfg_file),
    ]
    try:
        res = runner.run(cmd, cwd=pad_dir, timeout=600)
        log_lines.append("$ " + " ".join(cmd))
        if getattr(res, "stdout", ""):
            log_lines.append(res.stdout)
        if not res.not_found and res.returncode == 0 and def_file.is_file():
            used_real = True
        else:
            log_lines.append("[padring] binary unavailable/failed — using deterministic pad-ring assembly.")
    except Exception as exc:  # noqa: BLE001
        log_lines.append(f"[padring] runner error: {exc} — using deterministic pad-ring assembly.")

    if not def_file.is_file():
        def_file.write_text(_render_def(cfg, design))
    report.def_file = f"padring/{def_file.name}"
    _emit(report.def_file, "def", "pad/corner/filler placement")

    # 3. SVG preview (always produced).
    svg_file = pad_dir / f"{design}.svg"
    if not svg_file.is_file():
        svg_file.write_text(_render_svg(cfg, design))
    report.svg = f"padring/{svg_file.name}"
    _emit(report.svg, "layout_preview", "pad-ring visual preview")

    # 4. Ring netlist.
    v_file = pad_dir / f"{design}.v"
    if not v_file.is_file():
        v_file.write_text(_render_verilog(cfg, design))
    report.verilog = f"padring/{v_file.name}"
    _emit(report.verilog, "netlist", "pad-ring Verilog netlist")

    # 5. LEF abstract.
    lef_file = pad_dir / f"{design}.lef"
    lef_file.write_text(_render_lef(cfg, design))
    report.lef = f"padring/{lef_file.name}"
    _emit(report.lef, "lef", "pad-ring abstract LEF")

    # 6. GDS — Python-native assembly is the primary path, no external binary required.
    gds_file = pad_dir / f"{top}_chip.gds"
    merge_stats: Dict[str, object] = {}
    gds_is_binary = False
    try:
        merge_stats = _merge_gds(gds_file, cfg, top, f"{top}_chip", workspace)
        gds_is_binary = True
        log_lines.append("[padring] Python-native gdstk assembly succeeded.")
        for key, value in merge_stats.items():
            log_lines.append(f"[padring] {key}={value}")
    except Exception as exc:  # noqa: BLE001
        log_lines.append(f"[padring] Python-native GDS assembly failed: {exc}")
        if used_real:
            kcmd = [_klayout(), "-zz", "-rd", f"in_def={def_file}", "-rd", f"out_file={gds_file}"]
            try:
                kres = runner.run(kcmd, cwd=pad_dir, timeout=600)
                log_lines.append("$ " + " ".join(kcmd))
                gds_is_binary = not kres.not_found and kres.returncode == 0 and gds_file.is_file()
            except Exception as klayout_exc:  # noqa: BLE001
                log_lines.append(f"[padring] klayout error: {klayout_exc}")
        if not gds_is_binary:
            raise
    report.gds = f"padring/{gds_file.name}"
    _emit(report.gds, "gds", "chip-level pad-ring GDSII (primary deliverable)")

    preview_file = pad_dir / f"{top}_chip_preview.png"
    if _render_gds_preview(gds_file, preview_file, f"{top} GF180 pad-ring assembly"):
        _emit(f"padring/{preview_file.name}", "layout_preview", "chip-level GDS preview with layer legend and scale bar")
    svg_render = pad_dir / f"{top}_chip.svg"
    if _render_gds_preview(gds_file, svg_render, f"{top} GF180 pad-ring assembly"):
        _emit(f"padring/{svg_render.name}", "layout_preview", "chip-level GDS SVG render")

    # Copy GDS into the standard gds/ dir so RENDER / signoff previews pick it up.
    gds_copy = gds_dir / f"{design}.gds"
    try:
        gds_copy.write_bytes(gds_file.read_bytes())
        register_artifact(artifacts, path=f"gds/{gds_copy.name}", kind="gds", stage=stage, base=workspace,
                          summary="pad-ring GDS (workspace gds/ copy)")
    except Exception:  # noqa: BLE001
        pass

    pad_summary = _pad_summary(cfg)
    report.design = design
    report.pad_summary = pad_summary
    report.deliverables = deliverables
    report.used_real_tools = gds_is_binary
    W, H = cfg["die_um"]
    report.metrics = {
        "config": config_id,
        "pdk": cfg["pdk"],
        "die_width_um": W,
        "die_height_um": H,
        "die_area_um2": round(W * H, 2),
        "used_real_tools": report.used_real_tools,
        **{f"pads_{k}": v for k, v in pad_summary.items()},
        **{f"assembly_{k}": v for k, v in merge_stats.items()},
    }
    report.summary = (
        f"Assembled {config_id} pad ring '{design}' ({pad_summary['total_cells']} cells: "
        f"{pad_summary['total_io']} IO + 4 corners) on {W:g}x{H:g} um die. "
        f"Deliverables: {', '.join(deliverables)}."
    )

    log_text = "\n".join(log_lines) + "\n"
    (logs_dir / "padring.log").write_text(log_text)
    (pad_dir / "padring.log").write_text(log_text)
    register_artifact(artifacts, path="logs/padring.log", kind="log", stage=stage, base=workspace)
    register_artifact(artifacts, path="padring/padring.log", kind="log", stage=stage, base=workspace)
    report.raw_log_paths.append("logs/padring.log")
    report.raw_log_paths.append("padring/padring.log")
    report.artifacts = artifacts
    return report


__all__ = ["run_padring", "GF180_V1", "SUPPORTED_CONFIGS"]
