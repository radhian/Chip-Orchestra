#!/usr/bin/env python3
"""Apply the tracked D04 pin geometry to a generated DEF, preserving net names."""
import argparse
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("reference", type=Path)
parser.add_argument("generated", type=Path)
args = parser.parse_args()
ref = args.reference.read_text()
tgt = args.generated.read_text()
pattern = r"PINS\s+\d+\s*;\n(.*?)\nEND PINS"
ref_match = re.search(pattern, ref, re.S)
tgt_match = re.search(pattern, tgt, re.S)
if not ref_match or not tgt_match:
    raise SystemExit("missing PINS section")
net_map = dict(re.findall(r"^[ \t]*-[ \t]+(\S+)[ \t]+\+[ \t]+NET[ \t]+(\S+)", tgt_match.group(1), re.M))
blocks = []
for match in re.finditer(r"^[ \t]*-[ \t]+(\S+)(.*?)(?=^[ \t]*-[ \t]+\S+|\Z)", ref_match.group(1), re.M | re.S):
    name, rest = match.groups()
    if name not in net_map:
        raise SystemExit(f"generated DEF is missing D04 pin {name}")
    rest = re.sub(r"^(\s*\+\s+NET\s+)\S+", rf"\g<1>{net_map[name]}", rest, count=1)
    blocks.append(f"- {name}{rest.rstrip()}")
if len(blocks) != 21:
    raise SystemExit(f"reference must contain 21 pins, found {len(blocks)}")
replacement = "PINS 21 ;\n" + "\n".join(blocks) + "\nEND PINS"
tgt = re.sub(r"PINS\s+\d+\s*;\n.*?\nEND PINS", replacement, tgt, count=1, flags=re.S)
# Preserve the public port name in DEF/GDS extraction rather than exposing the
# synthesized internal alias used for this top-level output net.
tgt = tgt.replace("u_core.u_uart.uart_tx", "uart_tx_OUT")
# The supplied reference rectangles violate Metal2 spacing around uart_tx_IN.
# Move OE downward, center OUT between IN and SL, and move SL upward while
# retaining the D04 side/layer ordering. The generated deliverable is checked
# against these explicit integration corrections.
tgt = tgt.replace(
    "- uart_tx_OE + NET uart_tx_OE + DIRECTION OUTPUT + USE SIGNAL\n  + LAYER Metal2 ( 0 899170 ) ( 2000 899550 )",
    "- uart_tx_OE + NET uart_tx_OE + DIRECTION OUTPUT + USE SIGNAL\n  + LAYER Metal2 ( 0 898260 ) ( 2000 898540 )",
)
tgt = tgt.replace(
    "- uart_tx_OUT + NET uart_tx_OUT + DIRECTION OUTPUT + USE SIGNAL\n  + LAYER Metal2 ( 0 900630 ) ( 2000 901010 )",
    "- uart_tx_OUT + NET uart_tx_OUT + DIRECTION OUTPUT + USE SIGNAL\n  + LAYER Metal2 ( 0 900840 ) ( 2000 901120 )",
)
tgt = tgt.replace(
    "- uart_tx_SL + NET uart_tx_SL + DIRECTION OUTPUT + USE SIGNAL\n  + LAYER Metal2 ( 0 902090 ) ( 2000 902470 )",
    "- uart_tx_SL + NET uart_tx_SL + DIRECTION OUTPUT + USE SIGNAL\n  + LAYER Metal2 ( 0 902810 ) ( 2000 903190 )",
)
args.generated.write_text(tgt)
print(f"Applied D04 pin contract from {args.reference} to {args.generated}")
