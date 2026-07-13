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
