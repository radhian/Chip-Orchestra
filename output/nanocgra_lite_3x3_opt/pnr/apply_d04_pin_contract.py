#!/usr/bin/env python3
"""Apply the reviewer-authoritative D04 pin geometry to a routed DEF.

Overrides ALL 21 D04 pin rectangles from the tracked D04.def reference so the
deliverable exactly matches the reviewer's authoritative pad-side pin
locations. Preserves router-generated net names and routes for signal pins.
"""
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
if len(reference_pins) != 21:
    raise SystemExit(f"reference DEF must contain 21 pins, found {len(reference_pins)}")
if len(generated_pins) != 21:
    raise SystemExit(f"generated DEF must contain 21 pins, found {len(generated_pins)}")

# Enforce every pin from the reviewer-authoritative D04 reference, preserving
# whatever net name the router assigned in the generated DEF.
for pin_name, ref_block in reference_pins.items():
    if pin_name not in generated_pins:
        raise SystemExit(f"generated DEF is missing D04 pin {pin_name}")
    net_match = re.search(r"\+\s+NET\s+(\S+)", generated_pins[pin_name])
    if not net_match:
        raise SystemExit(f"generated DEF pin {pin_name} has no net")
    generated_pins[pin_name] = re.sub(
        r"^(\s*-\s+\S+\s+\+\s+NET\s+)\S+",
        rf"\g<1>{net_match.group(1)}",
        ref_block,
        count=1,
    )

replacement_body = "\n".join(generated_pins[name] for name in reference_pins)
generated = (
    generated[: generated_match.start(1)]
    + replacement_body
    + generated[generated_match.end(1) :]
)

# Preserve the public port name in DEF/GDS extraction rather than exposing the
# synthesized internal alias used for this top-level output net.
generated = generated.replace("u_core.u_uart.uart_tx", "uart_tx_OUT")

args.generated.write_text(generated)
print(
    f"Applied all 21 D04 pin geometries from {args.reference} to {args.generated}; "
    "router-generated signal routes preserved"
)
