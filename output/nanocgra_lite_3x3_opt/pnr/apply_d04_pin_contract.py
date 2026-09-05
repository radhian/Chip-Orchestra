#!/usr/bin/env python3
"""Apply only the disjoint D04 PG-pin geometry to a routed DEF."""
import argparse
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("reference", type=Path)
parser.add_argument("generated", type=Path)
args = parser.parse_args()

reference = args.reference.read_text()
generated = args.generated.read_text()
pins_pattern = r"PINS\s+\d+\s*;\n(.*?)\nEND PINS"
reference_match = re.search(pins_pattern, reference, re.S)
generated_match = re.search(pins_pattern, generated, re.S)
if not reference_match or not generated_match:
    raise SystemExit("missing PINS section")


def pin_blocks(body: str) -> dict[str, str]:
    return {
        match.group(1): match.group(0).rstrip()
        for match in re.finditer(
            r"^[ \t]*-[ \t]+(\S+).*?(?=^[ \t]*-[ \t]+\S+|\Z)",
            body,
            re.M | re.S,
        )
    }


reference_pins = pin_blocks(reference_match.group(1))
generated_pins = pin_blocks(generated_match.group(1))
if len(generated_pins) != 21:
    raise SystemExit(f"generated DEF must contain 21 pins, found {len(generated_pins)}")

for pin_name in ("vdd", "vss"):
    if pin_name not in reference_pins or pin_name not in generated_pins:
        raise SystemExit(f"missing D04 PG pin {pin_name}")
    net_match = re.search(r"\+\s+NET\s+(\S+)", generated_pins[pin_name])
    if not net_match:
        raise SystemExit(f"generated DEF pin {pin_name} has no net")
    replacement = re.sub(
        r"^(\s*-\s+\S+\s+\+\s+NET\s+)\S+",
        rf"\g<1>{net_match.group(1)}",
        reference_pins[pin_name],
        count=1,
    )
    generated_pins[pin_name] = replacement

replacement_body = "\n".join(generated_pins.values())
generated = generated[: generated_match.start(1)] + replacement_body + generated[generated_match.end(1) :]
generated = generated.replace("u_core.u_uart.uart_tx", "uart_tx_OUT")
args.generated.write_text(generated)
print(f"Applied D04 vdd/vss pin geometry from {args.reference} to {args.generated}; preserved router-generated signal pins")
