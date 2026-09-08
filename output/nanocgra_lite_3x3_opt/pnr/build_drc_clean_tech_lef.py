#!/usr/bin/env python3
"""Build a routing tech LEF whose M2/M3/M4 via landings meet Mn.3.

GF180's stock 0.28 x 0.38 um single-cut via landings have 0.1064 um^2
area, below the 0.1444 um^2 M2/M3/M4 requirement. This flow-owned LEF
keeps the foundry cut size and spacing unchanged while extending only the
M2/M3/M4 landing in its preferred direction to 0.28 x 0.52 um (0.1456
um^2). M1 and M5 geometry is left untouched.
"""
import argparse
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()

text = args.source.read_text()
fixed_count = 0
rule_count = 0


def legal_rectangle(direction: str) -> str:
    if direction == "H":
        return "RECT -0.260 -0.140 0.260 0.140 ;"
    return "RECT -0.140 -0.260 0.140 0.260 ;"


def legal_enclosure(direction: str) -> str:
    if direction == "H":
        return "0.130 0.010"
    return "0.010 0.130"


def patch_fixed(match: re.Match[str]) -> str:
    global fixed_count
    via_number, lower_direction, upper_direction, body = match.groups()
    directions = iter((lower_direction, upper_direction))

    def patch_metal(layer_match: re.Match[str]) -> str:
        layer_number = int(layer_match.group(2))
        direction = next(directions)
        if 2 <= layer_number <= 4:
            rectangle = legal_rectangle(direction)
        else:
            rectangle = layer_match.group(3)
        return f"{layer_match.group(1)}{rectangle}"

    patched, count = re.subn(
        r"(LAYER Metal(\d)\s*;\s*\n\s*)(RECT\s+[-0-9.]+\s+[-0-9.]+\s+[-0-9.]+\s+[-0-9.]+\s*;)",
        patch_metal,
        body,
    )
    if count != 2:
        raise SystemExit(f"Via{via_number}_{lower_direction}{upper_direction}: expected two metal rectangles, found {count}")
    fixed_count += 1
    return f"VIA Via{via_number}_{lower_direction}{upper_direction}  DEFAULT{patched}END Via{via_number}_{lower_direction}{upper_direction}"


text = re.sub(
    r"VIA Via([1-4])_([HV])([HV])\s+DEFAULT(.*?)END Via\1_\2\3",
    patch_fixed,
    text,
    flags=re.S,
)


def patch_rule(match: re.Match[str]) -> str:
    global rule_count
    via_number, lower_direction, upper_direction, body = match.groups()
    directions = iter((lower_direction, upper_direction))

    def patch_enclosure(enclosure_match: re.Match[str]) -> str:
        layer_number = int(enclosure_match.group(2))
        direction = next(directions)
        if 2 <= layer_number <= 4:
            values = legal_enclosure(direction)
        else:
            values = enclosure_match.group(3)
        return f"{enclosure_match.group(1)}{values} ;"

    patched, count = re.subn(
        r"(LAYER Metal(\d)\s*;\s*\n\s*ENCLOSURE\s+)([0-9.]+\s+[0-9.]+)\s*;",
        patch_enclosure,
        body,
    )
    if count != 2:
        raise SystemExit(f"Via{via_number}_GEN_{lower_direction}{upper_direction}: expected two enclosures, found {count}")
    rule_count += 1
    return f"VIARULE Via{via_number}_GEN_{lower_direction}{upper_direction} GENERATE{patched}END Via{via_number}_GEN_{lower_direction}{upper_direction}"


text = re.sub(
    r"VIARULE Via([1-4])_GEN_([HV])([HV])\s+GENERATE(.*?)END Via\1_GEN_\2\3",
    patch_rule,
    text,
    flags=re.S,
)

if fixed_count != 16 or rule_count != 16:
    raise SystemExit(f"expected 16 fixed vias and 16 generated rules, patched {fixed_count} and {rule_count}")

args.output.write_text(text)
print(f"Wrote {args.output}: M2/M3/M4 via landings are 0.28 x 0.52 um; cut size/spacing unchanged")
