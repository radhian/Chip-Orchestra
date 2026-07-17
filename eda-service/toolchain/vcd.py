"""Tolerant VCD -> wave-JSON parser.

Ported from GarudaChip's ``backend/garuda_api/vcd.py``. Handles the escaped
identifiers iverilog emits that strict parsers reject. Output is a compact JSON
structure the frontend can render as digital traces.
"""
from __future__ import annotations

import re
from typing import Any, Dict


def parse_vcd(text: str):
    """Return (names, widths, series): names[id]=label, widths[id]=bits,
    series[id]=[(time, int|None)] (None = x/z)."""
    names: Dict[str, str] = {}
    widths: Dict[str, int] = {}
    for m in re.finditer(r"\$var\s+\w+\s+(\d+)\s+(\S+)\s+([^$]+?)\s*\$end", text):
        w, vid, nm = int(m.group(1)), m.group(2), m.group(3).strip()
        names[vid] = nm.split("[")[0].strip().lstrip("\\")
        widths[vid] = w
    body = text.split("$enddefinitions", 1)[-1]
    toks = body.split()
    series: Dict[str, list] = {vid: [] for vid in names}
    cur, i = 0, 0
    while i < len(toks):
        t = toks[i]
        if t.startswith("#"):
            try:
                cur = int(t[1:])
            except ValueError:
                pass
        elif t and t[0] in "01xXzZ" and len(t) >= 2:  # scalar: value+id
            vid = t[1:]
            if vid in series:
                series[vid].append((cur, 1 if t[0] == "1" else 0 if t[0] == "0" else None))
        elif t and t[0] in "bB":  # vector: 'b1010' then id
            bits = t[1:]
            i += 1
            vid = toks[i] if i < len(toks) else ""
            if vid in series:
                try:
                    series[vid].append((cur, int(re.sub("[xXzZ]", "0", bits), 2)))
                except ValueError:
                    series[vid].append((cur, None))
        elif t and t[0] in "rR":  # real change: skip its id
            i += 1
        i += 1
    return names, widths, series


def to_wave_json(text: str, max_signals: int = 32, max_points: int = 2000) -> Dict[str, Any]:
    """Compact, frontend-friendly waveform structure:
    ``{tmax, signals: [{name, width, wave: [[t, value|null], ...]}]}``.
    """
    names, widths, series = parse_vcd(text)
    ids = _rank_by_activity([vid for vid in names if series.get(vid)], series)[:max_signals]
    tmax = max((series[v][-1][0] for v in ids if series[v]), default=0)
    out = []
    for vid in ids:
        pts = series[vid]
        if len(pts) > max_points:  # decimate very long traces
            step = len(pts) // max_points + 1
            pts = pts[::step]
        out.append({"name": names[vid], "width": widths[vid], "wave": [[t, v] for t, v in pts]})
    return {"tmax": tmax, "signals": out}


def _rank_by_activity(ids, series):
    """Busiest signals first; constants last. Testbench localparams get dumped
    as never-changing wires and used to fill the whole plot with flat lines
    (CLK_PERIOD, MAZE_N, …) while the actual DUT activity was cut off."""
    changing = [v for v in ids if len(series[v]) >= 3]
    flat = [v for v in ids if len(series[v]) < 3]
    changing.sort(key=lambda v: -len(series[v]))
    return changing + flat


def render_png(vcd_path, out_png, signals: str = "", max_traces: int = 12) -> "str | None":
    """Render the VCD to a step-plot PNG (GarudaChip's `_wave_to_png`) so the
    UI can SHOW the waveform, not just list design.vcd. Best-effort: returns the
    written path, or None when matplotlib is unavailable / nothing to plot."""
    from pathlib import Path

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        names, widths, series = parse_vcd(Path(vcd_path).read_text(errors="replace"))
        want = [s.strip() for s in re.split(r"[,\s]+", signals) if s.strip()]
        ids = [vid for vid in names if series[vid]
               and (not want or any(w.lower() in names[vid].lower() for w in want))]
        ids = _rank_by_activity(ids, series)[:max_traces]
        if not ids:
            return None
        tmax = max((series[vid][-1][0] for vid in ids), default=0) or 1
        fig, axes = plt.subplots(len(ids), 1, figsize=(10, 0.7 * len(ids) + 1),
                                 sharex=True, squeeze=False)
        for ax, vid in zip(axes[:, 0], ids):
            ts = [t for t, _ in series[vid]] + [tmax]
            vs = [v if v is not None else 0 for _, v in series[vid]]
            vs = vs + [vs[-1] if vs else 0]
            ax.step(ts, vs, where="post", linewidth=1.2)
            label = f"{names[vid]}[{widths[vid] - 1}:0]" if widths[vid] > 1 else names[vid]
            ax.set_ylabel(label, rotation=0, ha="right", va="center", fontsize=8)
            ax.margins(y=0.3)
            ax.grid(True, alpha=0.3)
            ax.set_yticks([])
        axes[-1, 0].set_xlabel("time")
        fig.tight_layout()
        fig.savefig(out_png, dpi=110)
        plt.close(fig)
        return str(out_png)
    except Exception:  # noqa: BLE001 - waveform render must never fail the stage
        return None
