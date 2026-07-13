#!/usr/bin/env python3
"""Timing / physical / sign-off / power summary card for NanoCGRA-Lite 3x3 OPT.
   All numbers are the FINAL locked opt values, cross-checked against the reports
   (flow_summary.md, sta.txt, fmax_sweep.txt, drc.txt, lvs_clean.txt,
   power_analysis.txt)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams.update({"font.family": "DejaVu Sans"})

R = "output/nanocgra_lite_3x3_opt/reports/"
assert "CLEAN" in open(R+"drc.txt").read()
assert "5325" in open(R+"lvs_clean.txt").read()

fig = plt.figure(figsize=(16, 9), facecolor="#0f1117")
fig.suptitle("NanoCGRA-Lite 3×3 OPT  —  Timing, Physical, Sign-off & Power Summary",
             fontsize=22, fontweight="bold", color="white", y=0.965)
fig.text(0.5, 0.905,
         "GF180MCU (gf180mcuD)  ·  gf180mcu_fd_sc_mcu7t5v0 5V 7-track  ·  5 metal layers  ·  target 10 MHz (100 ns)  ·  4-pin UART-only  ·  9 PEs (3×3) + 32 B SRAM",
         ha="center", fontsize=11.5, color="#9aa4b2")

ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
ax.set_xlim(0, 12); ax.set_ylim(0, 9)

def tile(x, y, w, h, title, value, sub, vcolor, accent, vfs=25):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                         mutation_aspect=1, linewidth=2, edgecolor=accent,
                         facecolor="#1a1f2b")
    ax.add_patch(box)
    ax.add_patch(FancyBboxPatch((x, y+h-0.12), w, 0.12, boxstyle="round,pad=0,rounding_size=0.0",
                 linewidth=0, facecolor=accent))
    ax.text(x+w/2, y+h-0.52, title, ha="center", va="center", fontsize=11.5,
            color="#9aa4b2", fontweight="bold")
    ax.text(x+w/2, y+h*0.45, value, ha="center", va="center", fontsize=vfs,
            color=vcolor, fontweight="bold")
    ax.text(x+w/2, y+0.32, sub, ha="center", va="center", fontsize=9.5, color="#7a8494")

G="#3fb950"; B="#58a6ff"; P="#bc8cff"; O="#f0883e"; R2="#ff7b72"; T="#39c5cf"

w, h, gap = 3.62, 2.35, 0.30
x0 = 0.55
row1 = 5.55
tile(x0+0*(w+gap), row1, w, h, "DIE SIZE", "466.6 x 466.6", "µm  (217,674 µm²)", B, B)
tile(x0+1*(w+gap), row1, w, h, "STANDARD CELLS", "5,296", "cells · 123,634 µm² cell area", P, P)
tile(x0+2*(w+gap), row1, w, h, "CORE UTILIZATION", "75 %", "4 I/O pins · 9 PEs + 32 B SRAM", O, O)

row2 = 2.90
tile(x0+0*(w+gap), row2, w, h, "SETUP SLACK (WNS)", "+76.72 ns", "MET · all paths · post-route STA", G, G)
tile(x0+1*(w+gap), row2, w, h, "HOLD SLACK (WNS)", "+0.82 ns", "MET · no violations", G, G)
tile(x0+2*(w+gap), row2, w, h, "DRC", "CLEAN", "0 violations · 41 rule tables", G, G)

# bottom strip: LVS + Fmax + power
by = 0.55
ax.add_patch(FancyBboxPatch((x0, by), w*3+gap*2, 1.95, boxstyle="round,pad=0.02,rounding_size=0.1",
             linewidth=2, edgecolor="#30363d", facecolor="#161b22"))
ax.text(x0+0.7, by+1.45, "LVS", fontsize=12, color="#9aa4b2", fontweight="bold")
ax.text(x0+0.7, by+0.75, "5325 = 5325", fontsize=19, color=G, fontweight="bold", ha="left")
ax.text(x0+0.7, by+0.22, "devices · 96/96 cells match uniquely", fontsize=9, color="#7a8494")

ax.text(x0+4.7, by+1.45, "MAX FMAX", fontsize=12, color="#9aa4b2", fontweight="bold")
ax.text(x0+4.7, by+0.75, "83.3 MHz", fontsize=19, color=T, fontweight="bold")
ax.text(x0+4.7, by+0.22, "12 ns, +0.72 ns · coarse 50 MHz · signoff 10 MHz", fontsize=8.3, color="#7a8494")

ax.text(x0+8.1, by+1.45, "POWER @10 MHz", fontsize=12, color="#9aa4b2", fontweight="bold")
ax.text(x0+8.1, by+0.75, "4.675 mW", fontsize=19, color=O, fontweight="bold")
ax.text(x0+8.1, by+0.22, "Int 3.813 / Sw 0.861 mW / Leak 1.13 µW · Seq 69.6% Comb 30.4%",
        fontsize=8.3, color="#7a8494")

fig.text(0.5, 0.02,
         "Sources: reports/flow_summary.md · reports/sta.txt · reports/fmax_sweep.txt (OpenROAD/OpenSTA post-route) · "
         "reports/drc.txt (KLayout GF180MCU deck) · reports/lvs_clean.txt (Magic+Netgen) · reports/power_analysis.txt",
         ha="center", fontsize=9.3, color="#6b7280")

fig.savefig("output/nanocgra_lite_3x3_opt/slides/timing_power_card.png", dpi=150,
            facecolor="#0f1117", bbox_inches="tight")
print("wrote timing_power_card.png")
