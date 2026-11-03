#!/usr/bin/env python3
"""Verify every D04 PG finger reaches the generated same-net core ring."""
import re
import sys
from pathlib import Path


def section(text: str, start: str, end: str) -> str:
    match = re.search(rf"{start}.*?;\s*(.*?){end}", text, re.S)
    return match.group(1) if match else ""


def block(body: str, name: str) -> str:
    match = re.search(rf"^[ \t]*-[ \t]+{re.escape(name)}\b(.*?)(?=^[ \t]*-[ \t]+\S+|\Z)", body, re.M | re.S)
    return match.group(1) if match else ""


def rectangles(pin_block: str) -> list[tuple[int, int, int, int]]:
    return [
        tuple(map(int, values))
        for values in re.findall(
            r"\+\s+LAYER\s+Metal2\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)",
            pin_block,
        )
    ]


def contains(rectangle: tuple[int, int, int, int], point: tuple[int, int]) -> bool:
    x1, y1, x2, y2 = rectangle
    x, y = point
    return min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} routed.def", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    text = path.read_text()
    pins = section(text, r"PINS\s+\d+", r"END PINS")
    special = section(text, r"SPECIALNETS\s+\d+", r"END SPECIALNETS")
    errors = []

    for net in ("vdd", "vss"):
        pin_rectangles = rectangles(block(pins, net))
        net_block = block(special, net)
        marker_match = re.search(
            rf"# D04_ALL_FINGERS_BEGIN {net}(.*?)# D04_ALL_FINGERS_END {net}",
            net_block,
            re.S,
        )
        if len(pin_rectangles) != 6:
            errors.append(f"{net}: expected 6 D04 Metal2 rectangles, found {len(pin_rectangles)}")
            continue
        if not marker_match:
            errors.append(f"{net}: missing generated all-finger connection block")
            continue
        routes = marker_match.group(1)
        metal2_vias = re.findall(
            r"NEW\s+Metal2\s+1200\s+\+\s+SHAPE\s+STRIPE\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(?:\*|-?\d+)\s+(?:\*|-?\d+)\s*\)\s+Via2_3200x1200",
            routes,
        )
        starts = [tuple(map(int, point)) for point in metal2_vias]
        connected = sum(any(contains(rectangle, point) for point in starts) for rectangle in pin_rectangles)
        if connected != 6 or len(starts) != 6:
            errors.append(f"{net}: only {connected}/6 boundary rectangles have one aligned Metal2-to-Metal3 via")
        expected_via3 = 6
        if routes.count("Via2_3200x1200") != 6:
            errors.append(f"{net}: expected 6 Via2 arrays")
        if routes.count("Via3_3200x1200") != expected_via3:
            errors.append(f"{net}: expected {expected_via3} Via3 arrays")
        if "Via4_" in routes:
            errors.append(f"{net}: custom finger routes must reuse PDN stripe/ring intersections, not add overlapping Via4 arrays")
        ring_layer = "Metal5" if net == "vdd" else "Metal4"
        ring_segments = [
            tuple(map(int, values))
            for values in re.findall(
                rf"NEW\s+{ring_layer}\s+3200\s+\+\s+SHAPE\s+STRIPE\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)",
                net_block,
            )
        ]
        if not any(max(abs(x2 - x1), abs(y2 - y1)) > 500000 for x1, y1, x2, y2 in ring_segments):
            errors.append(f"{net}: missing long {ring_layer} ring segment")
        if len(ring_segments) < 4:
            errors.append(f"{net}: ring is not accompanied by internal {ring_layer} stripes")

    for error in errors:
        print("ERROR: " + error, file=sys.stderr)
    if errors:
        return 1
    print("PASS: all 6 VDD and all 6 VSS D04 fingers reach the same-net M4/M5 ring and internal grid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
