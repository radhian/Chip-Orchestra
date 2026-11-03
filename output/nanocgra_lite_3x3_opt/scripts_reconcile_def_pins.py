from pathlib import Path
import re

ref_def = Path("../../../d04_ref/D04/project_defs/D/D04_D.def")
target_def = Path("pnr/nanocgra_lite_3x3_opt.def")

ref = ref_def.read_text()
tgt = target_def.read_text()

ref_pins = re.search(r"PINS\s+\d+\s*;\n(.*?)\nEND PINS", ref, re.S).group(1)
tgt_pins = re.search(r"PINS\s+\d+\s*;\n(.*?)\nEND PINS", tgt, re.S).group(1)

net_map = {}
for m in re.finditer(r"-\s+(\S+)\s+\+\s+NET\s+(\S+)", tgt_pins):
    net_map[m.group(1)] = m.group(2)

lines = []
for block in re.finditer(r"-\s+(\S+)\s+\+\s+NET\s+(\S+)\s+\+\s+DIRECTION\s+(\S+)\s+\+\s+USE\s+(\S+)(.*?)(?=\n-\s+\S+\s+\+\s+NET|\Z)", ref_pins, re.S):
    name, _, direction, use, rest = block.groups()
    net = net_map.get(name, name)
    header = f"    - {name} + NET {net} + DIRECTION {direction} + USE {use}"
    body = []
    for line in rest.splitlines():
        if "+ LAYER" in line:
            coords = re.search(r"\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", line)
            scaled = [int(x) * 10 for x in coords.groups()]
            layer = re.search(r"\+ LAYER\s+(\S+)", line).group(1)
            body.append(f"      + LAYER {layer} ( {scaled[0]} {scaled[1]} ) ( {scaled[2]} {scaled[3]} )")
        elif "+ FIXED" in line:
            body.append("      + FIXED ( 0 0 ) N ;")
    lines.append(header + "\n" + "\n".join(body))

new_pins = "PINS 21 ;\n" + "\n".join(lines) + "\nEND PINS"
tgt = re.sub(r"PINS\s+\d+\s*;\n.*?\nEND PINS", new_pins, tgt, flags=re.S)
target_def.write_text(tgt)
print("Reconciled DEF pins to D04_D.def geometry with current routed net names")
