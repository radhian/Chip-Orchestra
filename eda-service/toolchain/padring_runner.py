"""GF180MCU pad-ring assembly stage.

Runs during the *signoff* phase (after PNR) and assembles a chip-level I/O pad
ring around the hardened core, emitting the tape-out deliverable set:

* ``padring/<design>_padring.cfg`` - the resolved ``gf180-v1`` config (input)
* ``padring/<design>_padring.def`` - pad/corner/filler placement
* ``padring/<design>_padring.gds`` - chip-level GDSII (primary deliverable)
* ``padring/<design>_padring.lef`` - abstract for downstream assembly
* ``padring/<design>_padring.svg`` - visual preview
* ``padring/<design>_padring.v``   - ring netlist

Mirrors the reference flow (https://github.com/JuanMoya/padring_gf180): the
``padring`` tool consumes a ``.cfg`` + IO LEFs to produce a DEF, which KLayout
(``def2stream``) then streams to GDS.

Like the other runners this stage is *best-effort*: it shells out to the real
``padring`` / KLayout binaries through the injectable :class:`CommandRunner`,
and when those tools (or the GF180 PDK) are unavailable it degrades to writing
deterministic deliverable files so the pad-ring deliverable always exists and
the pipeline stays exercisable in dev / CI. Only the ``gf180-v1`` config is
supported; any other value (``none`` / unset) is a no-op success.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

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
    # pad class -> (cell, count)
    "pads": {
        "analog": ("gf180mcu_fd_io__asig_5p0", 60),
        "bidir": ("gf180mcu_fd_io__bi_t", 20),
        "dvdd": ("gf180mcu_fd_io__dvdd", 4),
        "dvss": ("gf180mcu_fd_io__dvss", 4),
        "clk": ("gf180mcu_fd_io__in_s", 1),
        "rst_n": ("gf180mcu_fd_io__in_c", 1),
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

    # Ordered flat list of pads.
    flat: List[str] = []
    for name, (_, count) in cfg["pads"].items():
        flat += [name] * count
    n = len(flat)
    per_edge = max(1, (n + 3) // 4)

    rects = []
    idx = 0
    for edge in range(4):
        edge_pads = flat[edge * per_edge:(edge + 1) * per_edge]
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


def _write_gds(path: Path, cfg: Dict, design: str) -> bool:
    """Write a real GDSII via gdstk when available; else a placeholder.

    Returns True when a binary GDS was produced by gdstk.
    """
    try:
        import gdstk
    except Exception:  # noqa: BLE001
        # Deterministic placeholder so the deliverable always exists.
        W, H = cfg["die_um"]
        path.write_text(
            f"# GDSII placeholder for {design} ({cfg['config_id']})\n"
            f"# die {W:g} x {H:g} um; gdstk unavailable in this environment.\n"
        )
        return False
    lib = gdstk.Library()
    cell = lib.new_cell(design)
    W, H = cfg["die_um"]
    rects, corner = _pad_ring_rects(cfg)
    cell.add(gdstk.rectangle((0, 0), (W, H), layer=235, datatype=0))       # PR boundary
    for cx, cy in ((0, 0), (W - corner, 0), (0, H - corner), (W - corner, H - corner)):
        cell.add(gdstk.rectangle((cx, cy), (cx + corner, cy + corner), layer=10, datatype=0))
    for x, y, w, h, _cls in rects:
        cell.add(gdstk.rectangle((x, y), (x + w, y + h), layer=30, datatype=0))
    lib.write_gds(str(path))
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

    # 6. GDS — try KLayout def2stream, else gdstk / placeholder. Primary deliverable.
    gds_file = pad_dir / f"{design}.gds"
    gds_from_klayout = False
    if used_real:
        kcmd = [_klayout(), "-zz", "-rd", f"in_def={def_file}", "-rd", f"out_file={gds_file}"]
        try:
            kres = runner.run(kcmd, cwd=pad_dir, timeout=600)
            log_lines.append("$ " + " ".join(kcmd))
            if not kres.not_found and kres.returncode == 0 and gds_file.is_file():
                gds_from_klayout = True
        except Exception as exc:  # noqa: BLE001
            log_lines.append(f"[padring] klayout error: {exc}")
    gds_is_binary = gds_from_klayout
    if not gds_file.is_file():
        gds_is_binary = _write_gds(gds_file, cfg, design)
    report.gds = f"padring/{gds_file.name}"
    _emit(report.gds, "gds", "chip-level pad-ring GDSII (primary deliverable)")

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
    report.used_real_tools = used_real and (gds_from_klayout or gds_is_binary)
    W, H = cfg["die_um"]
    report.metrics = {
        "config": config_id,
        "pdk": cfg["pdk"],
        "die_width_um": W,
        "die_height_um": H,
        "die_area_um2": round(W * H, 2),
        "used_real_tools": report.used_real_tools,
        **{f"pads_{k}": v for k, v in pad_summary.items()},
    }
    report.summary = (
        f"Assembled {config_id} pad ring '{design}' ({pad_summary['total_cells']} cells: "
        f"{pad_summary['total_io']} IO + 4 corners) on {W:g}x{H:g} um die. "
        f"Deliverables: {', '.join(deliverables)}."
    )

    (logs_dir / "padring.log").write_text("\n".join(log_lines) + "\n")
    register_artifact(artifacts, path="logs/padring.log", kind="log", stage=stage, base=workspace)
    report.raw_log_paths.append("logs/padring.log")
    report.artifacts = artifacts
    return report


__all__ = ["run_padring", "GF180_V1", "SUPPORTED_CONFIGS"]
