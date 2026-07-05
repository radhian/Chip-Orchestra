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
    ids = [vid for vid in names if series.get(vid)]
    ids = ids[:max_signals]
    tmax = max((series[v][-1][0] for v in ids if series[v]), default=0)
    out = []
    for vid in ids:
        pts = series[vid]
        if len(pts) > max_points:  # decimate very long traces
            step = len(pts) // max_points + 1
            pts = pts[::step]
        out.append({"name": names[vid], "width": widths[vid], "wave": [[t, v] for t, v in pts]})
    return {"tmax": tmax, "signals": out}
