import pya
import sys

# KLayout -rd variables are exposed as globals.
in_gds = globals().get("in_gds")
out_gds = globals().get("out_gds")
if not in_gds or not out_gds:
    raise SystemExit("missing -rd in_gds=<path> -rd out_gds=<path>")

layout = pya.Layout()
layout.read(in_gds)
top = layout.top_cell()
if top is None:
    raise SystemExit("no top cell found")

# GF180 density deck counts drawn + dummy purposes for each metal layer.
# Add electrically inert dummy-purpose fill on upper metals to close global density.
# Layers are from GF180 density.drc:
#   Metal2 dummy: 36/4, Metal3 dummy: 42/4, Metal4 dummy: 46/4, Metal5 dummy: 81/4
layers = [(36, 4), (42, 4), (46, 4), (81, 4)]

bbox = top.bbox()
margin = int(round(10.0 / layout.dbu))
step = int(round(10.0 / layout.dbu))
size = int(round(6.0 / layout.dbu))

x0 = bbox.left + margin
y0 = bbox.bottom + margin
x1 = bbox.right - margin
y1 = bbox.top - margin

inserted = 0
for layer_num, datatype in layers:
    li = layout.layer(layer_num, datatype)
    y = y0
    row = 0
    while y + size <= y1:
        x = x0 + (step // 2 if row % 2 else 0)
        while x + size <= x1:
            top.shapes(li).insert(pya.Box(x, y, x + size, y + size))
            inserted += 1
            x += step
        row += 1
        y += step

layout.write(out_gds)
print(f"Wrote {out_gds}; inserted {inserted} dummy fill rectangles across {len(layers)} layers")
