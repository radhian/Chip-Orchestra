"""Visual render stage.

Produces PNG visuals for the report bundle:

* **schematic**  - Yosys ``show`` -> Graphviz ``.dot`` -> PNG (``dot``).
* **waveform**   - simulation VCD -> PNG via matplotlib (uses :mod:`toolchain.vcd`).
* **gds layout** - GDSII -> PNG via gdstk (fallback: KLayout batch script).
* **metrics**    - LibreLane headline metrics -> bar chart via matplotlib.

Every renderer is best-effort and independent: a missing tool/library skips
that one visual (recorded as a warning) rather than failing the stage.
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from runner import CommandRunner, default_runner

from .artifacts import register_artifact
from .reports import RenderReport
from . import harden_runner as hr
from . import vcd


def _yosys() -> str:
    return os.getenv("YOSYS_PATH") or os.getenv("YOSYS_BIN", "yosys")


def _dot() -> str:
    return os.getenv("DOT_PATH") or os.getenv("GRAPHVIZ_DOT", "dot")


def _klayout() -> str:
    return os.getenv("KLAYOUT_PATH") or os.getenv("KLAYOUT_BIN", "klayout")


def render_schematic(workspace: Path, top: str, runner: CommandRunner) -> Optional[str]:
    rtl_dir = workspace / "rtl"
    reports_dir = workspace / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    sources = hr.closure_files(rtl_dir, top)
    if not sources:
        sources = [p.name for p in sorted(rtl_dir.glob("*.*")) if p.suffix in (".v", ".sv")]
    if not sources:
        return None
    # closure_files returns names relative to rtl_dir; resolve to absolute paths.
    abs_sources = [str((rtl_dir / s).resolve()) for s in sources]
    dot_path = reports_dir / "schematic.dot"
    read_cmd = "; ".join([f"read_verilog -sv {s}" for s in abs_sources])
    script = f"{read_cmd}; hierarchy -top {top}; proc; opt_clean; show -format dot -prefix {reports_dir / 'schematic'} {top}"
    res = runner.run([_yosys(), "-p", script], cwd=workspace, timeout=300)
    if res.not_found or not dot_path.is_file():
        # yosys writes schematic.dot; if the prefix form failed, try common name
        alt = sorted(glob.glob(str(reports_dir / "*.dot")))
        if not alt:
            return None
        dot_path = Path(alt[-1])
    png_path = reports_dir / "schematic.png"
    dres = runner.run([_dot(), "-Tpng", str(dot_path), "-o", str(png_path)], cwd=workspace, timeout=120)
    if dres.not_found or not png_path.is_file():
        return None
    return "reports/schematic.png"


def render_waveform(workspace: Path, top: str) -> Optional[str]:
    waves_dir = workspace / "waves"
    reports_dir = workspace / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    vcds = sorted(glob.glob(str(waves_dir / "*.vcd")))
    if not vcds:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return None
    try:
        wave = vcd.to_wave_json(Path(vcds[0]).read_text(errors="replace"), max_signals=12)
    except Exception:  # noqa: BLE001
        return None
    signals = wave.get("signals", [])
    if not signals:
        return None
    tmax = max(1, wave.get("tmax", 1))
    fig, axes = plt.subplots(len(signals), 1, figsize=(10, max(2, 0.7 * len(signals))), sharex=True)
    if len(signals) == 1:
        axes = [axes]
    for ax, sig in zip(axes, signals):
        pts = [(t, v if v is not None else 0) for t, v in sig.get("wave", [])]
        if pts:
            xs = [p[0] for p in pts] + [tmax]
            ys = [p[1] for p in pts] + [pts[-1][1]]
            ax.step(xs, ys, where="post")
        ax.set_ylabel(sig.get("name", "")[:16], rotation=0, ha="right", va="center", fontsize=7)
        ax.set_yticks([])
        ax.margins(y=0.3)
    axes[-1].set_xlabel("time (ns)")
    fig.suptitle(f"{top} — simulation waveform", fontsize=10)
    fig.tight_layout()
    out = reports_dir / "waveform.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return "reports/waveform.png" if out.is_file() else None


def render_gds(workspace: Path, top: str, runner: CommandRunner) -> Optional[str]:
    gds_dir = workspace / "gds"
    reports_dir = workspace / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    gds_files = sorted(glob.glob(str(gds_dir / "*.gds")))
    if not gds_files:
        return None
    # An existing LibreLane render is the best preview; reuse it if present.
    existing = gds_dir / f"{top}.png"
    out = reports_dir / "gds.png"
    if existing.is_file():
        out.write_bytes(existing.read_bytes())
        return "reports/gds.png"
    # Try gdstk (pure-python) for a polygon dump.
    try:
        import gdstk
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MplPoly
        from matplotlib.collections import PatchCollection

        lib = gdstk.read_gds(gds_files[0])
        cell = lib.top_level()[0]
        patches = []
        for poly in cell.get_polygons():
            patches.append(MplPoly(poly.points, closed=True))
        if not patches:
            return None
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.add_collection(PatchCollection(patches, alpha=0.5, edgecolor="k", linewidths=0.1))
        ax.autoscale()
        ax.set_aspect("equal")
        ax.set_title(f"{top} — GDSII layout")
        fig.savefig(out, dpi=120)
        plt.close(fig)
        return "reports/gds.png" if out.is_file() else None
    except Exception:  # noqa: BLE001
        pass
    # Fallback: KLayout batch screenshot.
    script = reports_dir / "_klayout_shot.py"
    script.write_text(
        "import pya\n"
        f"app = pya.Application.instance()\n"
        f"mw = app.main_window()\n"
        f"cv = mw.load_layout(r'{gds_files[0]}', 0)\n"
        f"lv = mw.current_view()\n"
        f"lv.max_hier()\n"
        f"lv.save_image(r'{out}', 1200, 1200)\n"
    )
    res = runner.run([_klayout(), "-z", "-rd", "-r", str(script)], cwd=workspace, timeout=300)
    if res.not_found or not out.is_file():
        return None
    return "reports/gds.png"


def render_metrics(workspace: Path, top: str) -> Optional[str]:
    reports_dir = workspace / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    chip = workspace / "exports" / "harden" / "chip"
    metrics = {}
    for mp in glob.glob(str(chip / "runs" / "**" / "metrics.json"), recursive=True):
        try:
            metrics = hr._slim_metrics(json.load(open(mp)))
            break
        except Exception:  # noqa: BLE001
            pass
    if not metrics:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return None
    keys = [k for k in ("cell_count", "die_area_um2", "core_area_um2", "util_pct", "wns_ns", "power_mw")
            if isinstance(metrics.get(k), (int, float))]
    if not keys:
        return None
    vals = [float(metrics[k]) for k in keys]
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(range(len(keys)), vals, color="#3b7dd8")
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(keys, rotation=30, ha="right", fontsize=8)
    ax.set_title(f"{top} — physical metrics")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:.3g}", ha="center", va="bottom", fontsize=7)
    fig.tight_layout()
    out = reports_dir / "metrics.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return "reports/metrics.png" if out.is_file() else None


def run_render(
    workspace: Path,
    top: str = "",
    opts: Optional[Dict] = None,
    runner: CommandRunner = default_runner,
    stage: str = "RENDER",
) -> RenderReport:
    opts = opts or {}
    workspace = Path(workspace)
    rtl_dir = workspace / "rtl"
    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    report = RenderReport(stage=stage)
    top = top or hr.pick_top(rtl_dir)
    report.top = top
    artifacts: List[dict] = []
    images: List[str] = []
    warnings: List[str] = []

    for label, fn in (
        ("schematic", lambda: render_schematic(workspace, top, runner)),
        ("waveform", lambda: render_waveform(workspace, top)),
        ("gds", lambda: render_gds(workspace, top, runner)),
        ("metrics", lambda: render_metrics(workspace, top)),
    ):
        try:
            rel = fn()
        except Exception as exc:  # noqa: BLE001
            rel = None
            warnings.append(f"{label} render error: {exc}")
        if rel:
            images.append(rel)
            register_artifact(artifacts, path=rel, kind="visual", stage=stage, base=workspace)
        else:
            warnings.append(f"{label} render skipped (tool/input unavailable)")

    report.images = images
    report.warnings = warnings
    report.metrics = {"rendered": len(images), "images": images}
    report.summary = f"Rendered {len(images)} visual(s): {', '.join(images) if images else 'none'}."
    report.artifacts = artifacts
    (logs_dir / "render.log").write_text(report.summary + "\n" + "\n".join(warnings) + "\n")
    register_artifact(artifacts, path="logs/render.log", kind="log", stage=stage, base=workspace)
    report.raw_log_paths.append("logs/render.log")
    return report


__all__ = ["run_render", "render_schematic", "render_waveform", "render_gds", "render_metrics"]
