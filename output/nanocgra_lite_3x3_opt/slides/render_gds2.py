#!/usr/bin/env python3
# KLayout render for 3x3 OPT: (1) full die metals-only; (2) zoomed detail crop.
import pya, os

gds = "output/nanocgra_lite_3x3_opt/gds/nanocgra_lite_3x3_opt.gds"
lyp = ".pdk/gf180mcuD/libs.tech/klayout/tech/gf180mcu.lyp"

def log(m): print(m, flush=True)

KEEP = {33, 34, 35, 36, 38, 40, 41, 42, 46, 81}

lv = pya.LayoutView()
lv.load_layout(gds, 0)
lv.max_hier()
if os.path.exists(lyp):
    lv.load_layer_props(lyp)
    log("lyp loaded")

ly = lv.active_cellview().layout()
top = ly.top_cell()
b = top.dbbox()
log("die um %.2f x %.2f" % (b.width(), b.height()))

lv.set_config("background-color", "#0a0a12")
lv.set_config("grid-visible", "false")
lv.set_config("text-visible", "false")

itr = lv.begin_layers()
kept = 0
while not itr.at_end():
    lp = itr.current()
    sl = lp.source_layer
    node = lp.dup()
    node.visible = (sl in KEEP)
    if node.visible: kept += 1
    lv.set_layer_properties(itr, node)
    itr.next()
log("kept metal layer-nodes: %d" % kept)

lv.zoom_fit()
lv.save_image("output/nanocgra_lite_3x3_opt/slides/layout_full.png", 2000, 2000)
log("saved layout_full.png")

cx, cy = b.center().x, b.center().y
w = 55.0
lv.zoom_box(pya.DBox(cx - w, cy - w, cx + w, cy + w))
lv.save_image("output/nanocgra_lite_3x3_opt/slides/layout_zoom.png", 1600, 1600)
log("saved layout_zoom.png")
