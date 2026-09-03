#!/usr/bin/env python3
"""Audit canonical GDS for forbidden dummy layers and required physical cells."""
import argparse
import sys
from pathlib import Path

FORBIDDEN = [(34, 4), (36, 4), (42, 4), (46, 4), (81, 4), (53, 4)]
PREFIX = "gf180mcu_fd_sc_mcu7t5v0__"
FILLERS = {PREFIX + "fill_16", PREFIX + "fill_8", PREFIX + "fill_4", PREFIX + "fill_2", PREFIX + "fill_1"}
REQUIRED = {PREFIX + "endcap", PREFIX + "filltie"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gds", type=Path)
    args = parser.parse_args()
    try:
        import pya
    except ImportError:
        print("ERROR: KLayout Python module 'pya' is unavailable", file=sys.stderr)
        return 2
    if not args.gds.is_file() or args.gds.stat().st_size == 0:
        print(f"ERROR: missing or empty GDS: {args.gds}", file=sys.stderr)
        return 2
    layout = pya.Layout()
    layout.read(str(args.gds))
    tops = list(layout.top_cells())
    errors = []
    if len(tops) != 1 or tops[0].name != "NanoCGRA_Lite":
        errors.append(f"expected sole top NanoCGRA_Lite, found {[c.name for c in tops]}")
    top = tops[0] if tops else None
    present = {cell.name for cell in layout.each_cell()}
    if top is not None:
        reachable = {layout.cell(index).name for index in top.called_cells()}
        reachable.add(top.name)
    else:
        reachable = set()
    missing = sorted(REQUIRED - reachable)
    if missing:
        errors.append("missing required reachable physical cells: " + ", ".join(missing))
    used_fillers = sorted(FILLERS & reachable)
    if not used_fillers:
        errors.append("no approved fill_16/8/4/2/1 cell is reachable from the top")
    forbidden_counts = []
    for layer, datatype in FORBIDDEN:
        index = layout.find_layer(layer, datatype)
        count = 0
        if index is not None and index >= 0:
            for cell in layout.each_cell():
                count += sum(1 for _ in cell.shapes(index).each())
        if count:
            forbidden_counts.append(f"{layer}/{datatype}={count}")
    if forbidden_counts:
        errors.append("forbidden dummy-purpose shapes found: " + ", ".join(forbidden_counts))
    else:
        print("forbidden dummy-purpose shapes=NONE")
    if top is not None:
        bbox = top.bbox()
        width = bbox.width() * layout.dbu
        height = bbox.height() * layout.dbu
        print(f"GDS top={top.name} bbox={width:.3f}x{height:.3f}um cells={len(present)}")
        if abs(width - 550.0) > 0.001 or abs(height - 550.0) > 0.001:
            errors.append(f"D04 bbox must be 550x550um, got {width:.3f}x{height:.3f}um")
    print("reachable fillers=" + (", ".join(used_fillers) if used_fillers else "NONE"))
    for error in errors:
        print("ERROR: " + error, file=sys.stderr)
    if errors:
        return 1
    print("PASS: canonical GDS has no forbidden dummy layers and has required physical-cell references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
