#!/usr/bin/env python3
"""Compose the KLayout-rendered die + detail crop into an annotated layout slide (3x3 OPT)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import Rectangle
import matplotlib.patches as mpatches

plt.rcParams.update({"font.family": "DejaVu Sans"})

SL = "output/nanocgra_lite_3x3_opt/slides/"
full = mpimg.imread(SL + "layout_full.png")
zoom = mpimg.imread(SL + "layout_zoom.png")

DIE = 466.56

fig = plt.figure(figsize=(16, 9.2), facecolor="white")
fig.suptitle("NanoCGRA-Lite 3×3 OPT  -  GDSII Layout  (KLayout render, GF180MCU 5-metal)",
             fontsize=18, fontweight="bold", y=0.975)

gs = fig.add_gridspec(1, 2, width_ratios=[1, 1], left=0.03, right=0.985,
                      top=0.90, bottom=0.11, wspace=0.06)

axf = fig.add_subplot(gs[0]); axf.imshow(full); axf.axis("off")
axf.set_title(f"Full die  —  {DIE:.1f} x {DIE:.1f} µm  (217,674 µm²)",
              fontsize=13, fontweight="bold", pad=8)
h, w = full.shape[0], full.shape[1]
frac = 110.0/DIE
rw = w*frac; rh = h*frac
rx = w/2 - rw/2; ry = h/2 - rh/2
axf.add_patch(Rectangle((rx, ry), rw, rh, fill=False, edgecolor="#ff3b3b", lw=2.2))

axz = fig.add_subplot(gs[1]); axz.imshow(zoom); axz.axis("off")
axz.set_title("Core detail  —  110 x 110 µm  (routed std-cell rows + PDN)",
              fontsize=13, fontweight="bold", pad=8)
for sp in axz.spines.values():
    sp.set_visible(True); sp.set_edgecolor("#ff3b3b"); sp.set_linewidth(2.2)

handles = [
    mpatches.Patch(color="#c9d100", label="Metal1 (std-cell rails / signal)"),
    mpatches.Patch(color="#9b4d9b", label="Metal2 (vertical routing / straps)"),
    mpatches.Patch(color="#e08a1e", label="Upper metals M3-M5 / PDN"),
    mpatches.Patch(color="#3fbfbf", label="Vias / Contacts"),
]
fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=11,
           frameon=False, bbox_to_anchor=(0.5, 0.045))
fig.text(0.5, 0.012,
         "Streamed with KLayout (DEF->GDS, merged std-cell GDS)  ·  top cell NanoCGRA_Lite  ·  "
         "DRC CLEAN (0 violations)  ·  LVS 5325 = 5325 devices  ·  75% utilization  ·  4-pin UART-only  ·  9 PEs (3×3) + 32 B SRAM",
         ha="center", fontsize=9.6, color="#444444")

fig.savefig(SL + "layout.png", dpi=140, facecolor="white", bbox_inches="tight")
print("wrote layout.png")
