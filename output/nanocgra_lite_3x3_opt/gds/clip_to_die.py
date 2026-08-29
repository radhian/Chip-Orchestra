import pya

in_gds = globals().get("in_gds")
out_gds = globals().get("out_gds")
die_size_um = float(globals().get("die_size_um", 550.0))
if not in_gds or not out_gds:
    raise SystemExit("missing -rd in_gds=<path> -rd out_gds=<path>")

layout = pya.Layout()
layout.read(in_gds)
top = layout.top_cell()
if top is None:
    raise SystemExit("no top cell found")

die = pya.Box(0, 0, int(round(die_size_um / layout.dbu)), int(round(die_size_um / layout.dbu)))

for li in layout.layer_indices():
    shapes = top.shapes(li)
    texts = []
    region = pya.Region()
    for s in shapes.each():
        if s.is_text():
            texts.append(s.text)
        elif s.is_box() or s.is_polygon() or s.is_path():
            region.insert(s.polygon)
    clipped = region & pya.Region(die)
    shapes.clear()
    for poly in clipped.each():
        shapes.insert(poly)
    for text in texts:
        shapes.insert(text)

layout.write(out_gds)
print(f"Clipped {in_gds} to 0..{die_size_um}um and wrote {out_gds}")
