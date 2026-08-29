import pya
import re
from pathlib import Path

pins_text = Path("pnr/nanocgra_lite_3x3_opt.def").read_text()
pins = re.search(r"PINS\s+\d+\s*;\n(.*?)\nEND PINS", pins_text, re.S).group(1)
centers = []
for block in re.finditer(r"-\s+(\S+)\s+\+\s+NET\s+\S+.*?(?=\n\s*-\s+\S+\s+\+\s+NET|\Z)", pins, re.S):
    name = block.group(1)
    rects = re.findall(r"\+ LAYER\s+Metal2\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", block.group(0))
    xs, ys = [], []
    for x1, y1, x2, y2 in rects:
        xs += [int(x1), int(x2)]
        ys += [int(y1), int(y2)]
    if xs:
        centers.append((name, ((min(xs) + max(xs)) // 2) // 2, ((min(ys) + max(ys)) // 2) // 2))

for in_name, out_name in [
    ("gds/nanocgra_lite_3x3_opt.gds", "gds/nanocgra_lite_3x3_opt_tmp.gds"),
    ("gds/nanocgra_lite_3x3_opt_filled.gds", "gds/nanocgra_lite_3x3_opt_filled_tmp.gds"),
]:
    layout = pya.Layout()
    layout.read(in_name)
    top = layout.top_cell()
    old_li = layout.find_layer(36, 10)
    label_polys = []
    if old_li >= 0:
        for shape in top.shapes(old_li).each():
            if not shape.is_text():
                label_polys.append(shape.polygon)
        top.shapes(old_li).clear()
        for poly in label_polys:
            top.shapes(old_li).insert(poly)
    li = layout.layer(36, 10)
    for name, x, y in centers:
        top.shapes(li).insert(pya.Text(name, pya.Trans(0, False, x, y)))
    layout.write(out_name)
    Path(out_name).replace(in_name)
    print(f"Updated {len(centers)} D04 pin labels in {in_name}")
