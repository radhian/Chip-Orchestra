#!/usr/bin/env python3
"""Connect the D04 Metal2 power pins to existing Metal4 PDN stripes in a DEF."""
import argparse
import re
from pathlib import Path

ROUTES = {
    "vdd": [
        "      NEW Metal2 1200 + SHAPE STRIPE ( 80160 1099000 ) ( * 1042920 ) Via2_3200x1200",
        "      NEW Metal3 1200 + SHAPE STRIPE ( 80160 1042920 ) Via3_3200x1200",
    ],
    "vss": [
        "      NEW Metal2 1200 + SHAPE STRIPE ( 1000 100000 ) ( 40160 * ) Via2_3200x1200",
        "      NEW Metal3 1200 + SHAPE STRIPE ( 40160 100000 ) Via3_3200x1200",
    ],
}


def add_routes(text: str, net: str, routes: list[str]) -> str:
    section_match = re.search(r"SPECIALNETS\s+\d+\s*;(.*?)END SPECIALNETS", text, re.S)
    if not section_match:
        raise SystemExit("missing SPECIALNETS section")
    body = section_match.group(1)
    net_match = re.search(
        rf"(^[ \t]*-[ \t]+{re.escape(net)}\b.*?)(\s*;)(?=\s*(?:^[ \t]*-[ \t]+\S+|\Z))",
        body,
        re.M | re.S,
    )
    if not net_match:
        raise SystemExit(f"missing SPECIALNET {net}")
    block = net_match.group(1)
    marker = routes[0].strip()
    if marker in block:
        return text
    replacement = block.rstrip() + "\n" + "\n".join(routes) + net_match.group(2)
    new_body = body[: net_match.start()] + replacement + body[net_match.end() :]
    return text[: section_match.start(1)] + new_body + text[section_match.end(1) :]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("def_file", type=Path)
    args = parser.parse_args()
    text = args.def_file.read_text()
    for net, routes in ROUTES.items():
        text = add_routes(text, net, routes)
    args.def_file.write_text(text)
    print(f"Connected D04 vdd/vss Metal2 pins to the existing Metal4 PDN in {args.def_file}")


if __name__ == "__main__":
    main()
