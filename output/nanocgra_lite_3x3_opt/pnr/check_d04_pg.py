#!/usr/bin/env python3
"""Check that D04 Metal2 PG BTerms physically enter same-net SPECIALNET routing."""
import re
import sys
from pathlib import Path


def section(text: str, start: str, end: str) -> str:
    match = re.search(rf"{start}.*?;\s*(.*?){end}", text, re.S)
    return match.group(1) if match else ""


def block(body: str, name: str) -> str:
    match = re.search(rf"^[ \t]*-[ \t]+{re.escape(name)}\b(.*?)(?=^[ \t]*-[ \t]+\S+|\Z)", body, re.M | re.S)
    return match.group(1) if match else ""


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
        pin_block = block(pins, net)
        net_block = block(special, net)
        rects = [tuple(map(int, r)) for r in re.findall(
            r"\+\s+LAYER\s+Metal2\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", pin_block)]
        routes = re.findall(r"(?:\+\s+ROUTED|\bNEW)\s+Metal2\b(.*?)(?=(?:\bNEW\s+Metal\d+)|;)", net_block, re.S)
        points = []
        for route in routes:
            points.extend((int(x), int(y)) for x, y in re.findall(r"\(\s*(-?\d+)\s+(-?\d+)(?:\s+-?\d+)?\s*\)", route))
        touches = any(min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)
                      for x, y in points for x1, y1, x2, y2 in rects)
        reaches_core = any(20000 <= x <= 1080000 and 20000 <= y <= 1080000 for x, y in points)
        has_via2 = "Via2_3200x1200" in net_block
        has_via3 = "Via3_3200x1200" in net_block
        if not rects:
            errors.append(f"{net}: no Metal2 boundary-pin rectangle")
        if not routes:
            errors.append(f"{net}: no same-net SPECIALNET Metal2 route")
        elif not touches:
            errors.append(f"{net}: Metal2 SPECIALNET route does not touch its boundary pin")
        elif not reaches_core:
            errors.append(f"{net}: Metal2 SPECIALNET route does not reach the core boundary/interior")
        if not has_via2 or not has_via3:
            errors.append(f"{net}: missing complete Metal2-Metal3-Metal4 via stack")
    for error in errors:
        print("ERROR: " + error, file=sys.stderr)
    if errors:
        return 1
    print("PASS: D04 Metal2 vdd/vss pins have same-net SPECIALNET routes reaching the core")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
