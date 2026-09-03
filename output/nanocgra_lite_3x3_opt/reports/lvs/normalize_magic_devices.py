#!/usr/bin/env python3
"""Convert Magic's GF180 four-terminal X-device records into SPICE MOS records.

Magic emits extracted nfet_05v0/pfet_05v0 geometry as four-terminal X calls.
Official GF180 CDL uses M records. Netgen otherwise treats the X calls as
undefined black boxes with numeric proxy pins, which defeats transistor-level
pin/property matching. This transformation preserves every extracted node and
all geometry parameters; it changes only the SPICE device record type.
"""
import argparse
import re
from pathlib import Path

DEVICE = re.compile(
    r"^X(?P<name>\S+)\s+(?P<drain>\S+)\s+(?P<gate>\S+)\s+(?P<source>\S+)\s+"
    r"(?P<bulk>\S+)\s+(?P<model>[np]fet_05v0)(?P<params>\s+.*)?$",
    re.IGNORECASE,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spice", type=Path)
    args = parser.parse_args()
    lines = args.spice.read_text().splitlines()
    converted = 0
    output = []
    for line in lines:
        match = DEVICE.match(line)
        if not match:
            output.append(line)
            continue
        fields = match.groupdict(default="")
        output.append(
            f"M{fields['name']} {fields['drain']} {fields['gate']} {fields['source']} "
            f"{fields['bulk']} {fields['model']}{fields['params']}"
        )
        converted += 1
    if converted == 0:
        raise SystemExit("no extracted GF180 MOS X-device records found")
    args.spice.write_text("\n".join(output) + "\n")
    print(f"Normalized {converted} extracted GF180 MOS devices in {args.spice}")


if __name__ == "__main__":
    main()
