#!/usr/bin/env python3
"""Connect every D04 PG finger to the generated M4/M5 core ring."""
import argparse
import re
from pathlib import Path

DBU_PER_UM = 2000
ROUTE_WIDTH = 1200
RING_WIDTH = 3200
VIA_HALF_WIDTH = 1600


def section(text: str, start: str, end: str) -> tuple[str, int, int]:
    match = re.search(rf"{start}.*?;\s*(.*?){end}", text, re.S)
    if not match:
        raise SystemExit(f"missing {start} section")
    return match.group(1), match.start(1), match.end(1)


def named_block(body: str, name: str) -> tuple[str, int, int]:
    match = re.search(
        rf"(^[ \t]*-[ \t]+{re.escape(name)}\b.*?)(\s*;)(?=\s*(?:^[ \t]*-[ \t]+\S+|\Z))",
        body,
        re.M | re.S,
    )
    if not match:
        raise SystemExit(f"missing block for {name}")
    return match.group(1), match.start(), match.end()


def pin_rectangles(pin_body: str, name: str) -> list[tuple[int, int, int, int]]:
    block, _, _ = named_block(pin_body, name)
    rectangles = [
        tuple(map(int, values))
        for values in re.findall(
            r"\+\s+LAYER\s+Metal2\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)",
            block,
        )
    ]
    if len(rectangles) != 6:
        raise SystemExit(f"{name}: expected 6 D04 Metal2 rectangles, found {len(rectangles)}")
    return rectangles


def ring_coordinate(net_block: str, layer: str, orientation: str) -> int:
    candidates = []
    pattern = rf"(?:\+\s+ROUTED|\bNEW)\s+{layer}\s+{RING_WIDTH}\s+\+\s+SHAPE\s+STRIPE\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)"
    for x1, y1, x2, y2 in re.findall(pattern, net_block):
        x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))
        if orientation == "horizontal" and y1 == y2 and abs(x2 - x1) > 500000:
            candidates.append(y1)
        elif orientation == "vertical" and x1 == x2 and abs(y2 - y1) > 500000:
            candidates.append(x1)
    if not candidates:
        raise SystemExit(f"missing {net_block[:20].strip()} {layer} {orientation} ring segment")
    return max(candidates) if orientation == "horizontal" else min(candidates)


def vertical_stripe_coordinate(net_block: str, near: int) -> int:
    candidates = []
    pattern = rf"(?:\+\s+ROUTED|\bNEW)\s+Metal4\s+{RING_WIDTH}\s+\+\s+SHAPE\s+STRIPE\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)"
    for x1, y1, x2, y2 in re.findall(pattern, net_block):
        x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))
        if x1 == x2 and abs(y2 - y1) > 500000:
            candidates.append(x1)
    if not candidates:
        raise SystemExit("missing same-net Metal4 vertical PDN stripe")
    return min(candidates, key=lambda coordinate: abs(coordinate - near))


def connection_routes(net: str, rectangles: list[tuple[int, int, int, int]], target: int, net_block: str) -> list[str]:
    routes = []
    if net == "vdd":
        for x1, y1, x2, y2 in sorted(rectangles):
            x = (x1 + x2) // 2
            y = (y1 + y2) // 2
            via_y = y - ROUTE_WIDTH // 2
            stripe_x = vertical_stripe_coordinate(net_block, x + 10000)
            routes.extend([
                f"      NEW Metal2 {ROUTE_WIDTH} + SHAPE STRIPE ( {x} {y} ) ( * {via_y} ) Via2_3200x1200",
                f"      NEW Metal3 {ROUTE_WIDTH} + SHAPE STRIPE ( {x} {via_y} ) ( * {target} ) ( {stripe_x} * ) Via3_3200x1200",
            ])
    else:
        for x1, y1, x2, y2 in sorted(rectangles, key=lambda rectangle: rectangle[1]):
            x = (x1 + x2) // 2
            y = (y1 + y2) // 2
            via_x = max(x + ROUTE_WIDTH // 2, VIA_HALF_WIDTH)
            routes.extend([
                f"      NEW Metal2 {ROUTE_WIDTH} + SHAPE STRIPE ( {x} {y} ) ( {via_x} * ) Via2_3200x1200",
                f"      NEW Metal3 {ROUTE_WIDTH} + SHAPE STRIPE ( {via_x} {y} ) ( {target} * ) Via3_3200x1200",
            ])
    return routes


def replace_connections(text: str, net: str, rectangles: list[tuple[int, int, int, int]]) -> str:
    special, special_start, special_end = section(text, r"SPECIALNETS\s+\d+", r"END SPECIALNETS")
    net_block, block_start, block_end = named_block(special, net)
    begin = f"      # D04_ALL_FINGERS_BEGIN {net}"
    end = f"      # D04_ALL_FINGERS_END {net}"
    net_block = re.sub(rf"\n?\s*# D04_ALL_FINGERS_BEGIN {net}.*?# D04_ALL_FINGERS_END {net}", "", net_block, flags=re.S)
    if net == "vdd":
        target = ring_coordinate(net_block, "Metal5", "horizontal")
    else:
        target = ring_coordinate(net_block, "Metal4", "vertical")
    addition = "\n" + begin + "\n" + "\n".join(connection_routes(net, rectangles, target, net_block)) + "\n" + end
    net_block = net_block.rstrip() + addition + "\n    ;"
    special = special[:block_start] + net_block + special[block_end:]
    return text[:special_start] + special + text[special_end:]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("def_file", type=Path)
    args = parser.parse_args()
    text = args.def_file.read_text()
    pins, _, _ = section(text, r"PINS\s+\d+", r"END PINS")
    rectangles = {net: pin_rectangles(pins, net) for net in ("vdd", "vss")}
    for net in ("vdd", "vss"):
        text = replace_connections(text, net, rectangles[net])
    args.def_file.write_text(text)
    print(f"Connected all 6 VDD and all 6 VSS D04 fingers to the generated PDN ring in {args.def_file}")


if __name__ == "__main__":
    main()
