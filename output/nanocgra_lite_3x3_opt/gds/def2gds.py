#!/usr/bin/env python3
# KLayout DEF -> GDS streaming for NanoCGRA_Lite (GF180MCU)
# Merges the standard-cell GDS so macros contain real device geometry.
# Invoked with klayout -zz -b -r def2gds.py -rd def_file=.. -rd out_gds=.. ...
import pya

opt = pya.LoadLayoutOptions()
cfg = opt.lefdef_config
cfg.map_file = map_file
cfg.lef_files = [tech_lef, cell_lef]
cfg.read_lef_with_def = False
cfg.dbu = 0.001
# 2 = never generate LEF macro geometry (rely on merged GDS for real device layers)
cfg.macro_resolution_mode = 2
cfg.produce_via_geometry = True
cfg.produce_routing = True
cfg.produce_special_routing = True

layout = pya.Layout()
layout.read(def_file, opt)
print("After DEF read: %d cells" % layout.cells())
for tc in layout.top_cells():
    print("   top:", tc.name)

# Merge standard-cell GDS (fills the empty macro cells created by the DEF reader)
layout.read(cell_gds)
print("After cell GDS merge: %d cells" % layout.cells())

ti = layout.cell(top_name)
if ti is None:
    print("ERROR: top cell %s not found" % top_name)
    raise SystemExit(1)

# KLayout's DEF reader represents generated vias as separate VIA_* helper cells.
# Make each helper's M1-M5 landing metal independently satisfy Mn.3 so a
# hierarchical top-level check does not depend on merging it with parent routes.
minimum_area_dbu2 = int(round(0.1444 / (layout.dbu * layout.dbu)))
patched_via_shapes = 0
metal_layers = [layout.layer(layer, 0) for layer in (34, 36, 42, 46, 81)]
for via_cell in [cell for cell in layout.each_cell() if cell.name.startswith("VIA_")]:
    for layer_index in metal_layers:
        for shape in list(via_cell.shapes(layer_index).each()):
            if not shape.is_box():
                continue
            box = shape.box
            if box.area() >= minimum_area_dbu2:
                continue
            if box.width() >= box.height():
                required_width = (minimum_area_dbu2 + box.height() - 1) // box.height()
                required_width += required_width % 2
                delta = required_width - box.width()
                box = pya.Box(box.left - delta // 2, box.bottom, box.right + delta // 2, box.top)
            else:
                required_height = (minimum_area_dbu2 + box.width() - 1) // box.width()
                required_height += required_height % 2
                delta = required_height - box.height()
                box = pya.Box(box.left, box.bottom - delta // 2, box.right, box.top + delta // 2)
            shape.box = box
            patched_via_shapes += 1
print("Patched %d generated via landing shapes to minimum area" % patched_via_shapes)

# Prune cells not referenced by the top hierarchy (unused std cells from merged GDS)
keep = set(ti.called_cells())
keep.add(ti.cell_index())
to_del = [c.cell_index() for c in layout.each_cell() if c.cell_index() not in keep]
for ci in to_del:
    layout.delete_cell(ci)
print("After prune: %d cells" % layout.cells())

wopt = pya.SaveLayoutOptions()
wopt.set_format_from_filename(out_gds)
layout.write(out_gds, wopt)
print("WROTE", out_gds)
