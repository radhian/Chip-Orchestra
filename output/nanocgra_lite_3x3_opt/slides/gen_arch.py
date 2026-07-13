#!/usr/bin/env python3
"""NanoCGRA-Lite 3x3 OPT architecture block diagram (Chip Orchestra style).
   *** 4-PIN UART-ONLY top-level interface ***
   Only clk / rst_n / uart_rx / uart_tx cross the chip boundary. Inside, an
   internal uart_bridge (UART-to-bus master) drives the 8-bit MMIO bus that
   fans out to 32 B SRAM, the memory-mapped UART, the 3x3 CGRA (9 PEs) and the
   Nano Controller FSM."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle

plt.rcParams.update({"font.family": "DejaVu Sans"})

fig = plt.figure(figsize=(17, 10.8), facecolor="white")
ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
ax.set_xlim(0, 17); ax.set_ylim(0, 10.8)

C = dict(soc="#334155", bus="#6d28d9", dec="#7c3aed", sram="#2563eb",
         cgra="#059669", pe="#10b981", uart="#d97706", ctrl="#dc2626",
         mem="#0f766e", bridge="#0891b2", pin="#0f172a")

def box(x, y, w, h, fc, ec, title, sub=None, tfs=13, sfs=9.5,
        tcolor="white", scolor="#e8fff4", rounding=0.10, lw=2):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle=f"round,pad=0.02,rounding_size={rounding}",
                       facecolor=fc, edgecolor=ec, linewidth=lw)
    ax.add_patch(p)
    if sub:
        ax.text(x+w/2, y+h*0.64, title, ha="center", va="center",
                fontsize=tfs, fontweight="bold", color=tcolor)
        ax.text(x+w/2, y+h*0.27, sub, ha="center", va="center",
                fontsize=sfs, color=scolor)
    else:
        ax.text(x+w/2, y+h/2, title, ha="center", va="center",
                fontsize=tfs, fontweight="bold", color=tcolor)
    return p

def arrow(x1, y1, x2, y2, color="#334155", lw=2.2, style="-|>", ms=14, ls="-"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=ms,
                        color=color, lw=lw, linestyle=ls,
                        shrinkA=0, shrinkB=0, zorder=5)
    ax.add_patch(a)

# ---- title ----
ax.text(8.5, 10.45, "NanoCGRA-Lite 3×3 OPT  —  4-Pin UART-Only SoC",
        ha="center", fontsize=22, fontweight="bold", color="#111827")
ax.text(8.5, 10.05,
        "3×3 CGRA (9 PEs) · Nano Controller FSM · 32 B SRAM · MMIO UART · on-chip UART-bridge master   ·   single clock domain, sync reset, 10 MHz",
        ha="center", fontsize=11.3, color="#6b7280")

# ---- SoC boundary ----
sx, sy, sw, sh = 2.05, 0.45, 9.75, 9.25
soc = FancyBboxPatch((sx, sy), sw, sh, boxstyle="round,pad=0.02,rounding_size=0.15",
                     facecolor="#f8fafc", edgecolor=C["soc"], linewidth=2.8, linestyle="--")
ax.add_patch(soc)
ax.text(sx+0.25, sy+sh-0.32, "NanoCGRA-Lite SoC  (chip boundary)",
        fontsize=11, fontweight="bold", color=C["soc"])

# ---- the ONLY 4 chip pins ----
pin_defs = [("clk", 8.85, C["pin"]), ("rst_n", 8.05, C["pin"]),
            ("uart_rx", 3.35, C["uart"]), ("uart_tx", 2.55, C["uart"])]
for name, py, col in pin_defs:
    # pin pad on boundary
    ax.add_patch(Rectangle((sx-0.14, py-0.11), 0.28, 0.22, facecolor=col,
                           edgecolor="white", lw=1.2, zorder=6))
    ax.text(sx-0.35, py, name, ha="right", va="center", fontsize=12.5,
            fontweight="bold", family="monospace", color=col)
# 4 PINS ONLY badge
badge = FancyBboxPatch((0.15, 5.35, ), 1.55, 1.5,
                       boxstyle="round,pad=0.03,rounding_size=0.12",
                       facecolor="#fff7ed", edgecolor=C["uart"], linewidth=2.4)
ax.add_patch(badge)
ax.text(0.92, 6.45, "4 PINS", ha="center", fontsize=17, fontweight="bold", color=C["uart"])
ax.text(0.92, 5.98, "ONLY", ha="center", fontsize=17, fontweight="bold", color=C["uart"])
ax.text(0.92, 5.58, "(was 39)", ha="center", fontsize=9.5, color="#9a3412")

# ---- uart_bridge (bus MASTER) ----
brx, bry, brw, brh = 2.45, 8.20, 4.35, 1.05
box(brx, bry, brw, brh, C["bridge"], "#155e75",
    "uart_bridge  —  UART-to-bus MASTER",
    "16-state FSM · decodes 3-byte packet [CMD][ADDR][DATA]  ·  sole bus master",
    tfs=12.5, sfs=8.6)
# clk / rst_n global feed to bridge (and chip)
arrow(sx-0.02, 8.85, brx, bry+brh*0.72, color=C["pin"], lw=1.6, ms=11)
arrow(sx-0.02, 8.05, brx, bry+brh*0.30, color=C["pin"], lw=1.6, ms=11)
ax.text(0.92, 7.35, "clk / rst_n →\nall blocks\n(single domain)",
        fontsize=8, color="#64748b", ha="center", style="italic")

# ---- MMIO bus ----
busx, busy, busw, bush = 2.45, 7.30, 9.05, 0.62
box(busx, busy, busw, bush, C["bus"], "#4c1d95",
    "Internal 8-bit MMIO Bus", "addr[7:0] · wdata[7:0] · rdata[7:0] · we / re strobes",
    tfs=12.5, sfs=8.8)
arrow(brx+brw*0.5, bry, brx+brw*0.5, busy+bush, color="#155e75", lw=2.6)
ax.text(brx+brw*0.5+0.15, bry-0.12, "master port", fontsize=7.6, color="#155e75", ha="left")

# ---- bus decoder ----
decx, decy, decw, dech = 2.45, 6.55, 9.05, 0.52
box(decx, decy, decw, dech, C["dec"], "#4c1d95",
    "Bus Decoder  —  address map → chip-selects", None, tfs=12)
arrow(busx+busw*0.5, busy, busx+busw*0.5, decy+dech, color="#4c1d95", lw=2.6)

# ---- peripheral row: SRAM / UART / Nano Controller ----
prow_y, prow_h = 4.65, 1.55
box(2.45, prow_y, 2.15, prow_h, C["sram"], "#1e3a8a",
    "32 B SRAM", "single-port\narbitrated:\nbridge / ctrl", tfs=13, sfs=8.6)
box(4.85, prow_y, 2.75, prow_h, C["uart"], "#92400e",
    "mem-mapped UART", "TX / RX  ·  TXDATA 0x80\nRXDATA 0x81 · STATUS 0x82", tfs=11.5, sfs=8.4)
box(7.85, prow_y, 3.65, prow_h, C["ctrl"], "#7f1d1d",
    "Nano Controller", "FSM (7 states): IDLE→RD_A→RD_B→LOAD\n→EXEC→STORE→DONE · drives CGRA + SRAM",
    tfs=12.5, sfs=8.2)
# decoder -> peripherals
arrow(3.5,  decy, 3.5,  prow_y+prow_h, color=C["sram"], lw=2.0)
arrow(6.2,  decy, 6.2,  prow_y+prow_h, color=C["uart"], lw=2.0)
arrow(9.65, decy, 9.65, prow_y+prow_h, color=C["ctrl"], lw=2.0)

# dashed feedback: bridge polls UART peripheral over the bus
arrow(sx-0.02, 3.35, 4.85, prow_y+prow_h*0.62, color=C["uart"], lw=2.2, ms=13)
arrow(4.85, prow_y+prow_h*0.30, sx-0.02, 2.55, color=C["uart"], lw=2.2, ms=13)
ax.text(2.25, 3.05, "serial RX / TX",
        fontsize=8.4, color=C["uart"], ha="left", style="italic", fontweight="bold")

# controller control + operand paths
arrow(9.65, prow_y, 9.65, 4.05, color=C["ctrl"], lw=1.6, style="-|>", ls=(0,(4,2)))
ax.text(10.15, 4.35, "run / load / en", fontsize=7.6, color=C["ctrl"], ha="center")
arrow(8.1, prow_y, 4.0, prow_y, color=C["ctrl"], lw=1.3, style="-|>", ls=(0,(4,2)))
ax.text(6.0, prow_y+0.13, "operand / result r/w", fontsize=7.6, color=C["ctrl"], ha="center")

# ---- CGRA (big) with 3x3 mesh ----
cx, cy, cw, ch = 2.45, 0.70, 9.05, 3.30
box(cx, cy, cw, ch, "#ecfdf5", C["cgra"], "", None, lw=2.6)
ax.text(cx+cw/2, cy+ch-0.24, "3×3 CGRA  —  9 reconfigurable PEs (square mesh, N/S/E/W routing)",
        ha="center", fontsize=12, fontweight="bold", color=C["cgra"])
arrow(cx+cw/2, prow_y, cx+cw/2, cy+ch, color=C["cgra"], lw=2.2)

NCOL, NROW = 3, 3
pw, phh = 2.35, 0.66
gapx = (cw - 0.7 - NCOL*pw) / (NCOL-1)
x0 = cx + 0.35
gapy = 0.22
y_bot = cy + 0.34
ys = [y_bot, y_bot + phh + gapy, y_bot + 2*(phh + gapy)]
centers = {}
for r in range(NROW):
    yy = ys[NROW-1-r]
    for c in range(NCOL):
        xx = x0 + c*(pw+gapx)
        box(xx, yy, pw, phh, C["pe"], "#047857", f"PE({r},{c})",
            "ALU+MAC · cfg", tfs=9.8, sfs=6.6)
        centers[(r,c)] = (xx+pw/2, yy+phh/2, xx, yy, pw, phh)

def dbl(x1,y1,x2,y2):
    arrow(x1,y1,x2,y2, color="#047857", lw=1.5, style="<|-|>", ms=8)
for r in range(NROW):
    for c in range(NCOL-1):
        xa=centers[(r,c)][2]+pw; ya=centers[(r,c)][1]
        xb=centers[(r,c+1)][2]; dbl(xa,ya,xb,ya)
for c in range(NCOL):
    for r in range(NROW-1):
        xa=centers[(r,c)][0]; ya=centers[(r,c)][3]
        yb=centers[(r+1,c)][3]+phh; dbl(xa,ya,xa,yb)

# ---- Memory map + serial protocol table (right) ----
mx, my, mw, mh = 12.15, 0.45, 4.55, 9.25
tbl = FancyBboxPatch((mx, my), mw, mh, boxstyle="round,pad=0.02,rounding_size=0.12",
                     facecolor="#ffffff", edgecolor=C["mem"], linewidth=2.4)
ax.add_patch(tbl)
ax.add_patch(Rectangle((mx, my+mh-0.68), mw, 0.68, facecolor=C["mem"], edgecolor="none"))
ax.text(mx+mw/2, my+mh-0.34, "Memory Map  (8-bit address)", ha="center",
        va="center", fontsize=13, fontweight="bold", color="white")

rows = [
    ("0x00 - 0x1F", "SRAM  (32 bytes)", C["sram"]),
    ("0x80", "UART  TXDATA", C["uart"]),
    ("0x81", "UART  RXDATA", C["uart"]),
    ("0x82", "UART  STATUS", C["uart"]),
    ("0x83", "UART  CTRL", C["uart"]),
    ("0x90 - 0x98", "CGRA  cfg0 .. cfg8 (9 PEs)", C["cgra"]),
    ("0x99 - 0x9B", "CGRA  opa / opb / res addr", C["cgra"]),
    ("0xA0", "START  (write triggers run)", C["ctrl"]),
    ("0xA1", "STATUS  { done, busy }", C["ctrl"]),
]
ry = my+mh-0.68
tbl_bot = my+2.35
rh = (my+mh-0.83 - tbl_bot)/len(rows)
for i,(addr, desc, col) in enumerate(rows):
    ry -= rh
    if i % 2 == 0:
        ax.add_patch(Rectangle((mx+0.05, ry), mw-0.1, rh, facecolor="#f1f5f9", edgecolor="none"))
    ax.add_patch(Rectangle((mx+0.12, ry+rh*0.22), 0.12, rh*0.56, facecolor=col, edgecolor="none"))
    ax.text(mx+0.42, ry+rh/2, addr, va="center", ha="left", fontsize=10,
            family="monospace", fontweight="bold", color="#0f172a")
    ax.text(mx+2.15, ry+rh/2, desc, va="center", ha="left", fontsize=10, color="#334155")

# serial protocol sub-panel at the bottom of the table
py0 = my+0.15
ax.add_patch(Rectangle((mx+0.12, py0), mw-0.24, 2.0, facecolor="#ecfeff",
                       edgecolor=C["bridge"], lw=1.6))
ax.text(mx+mw/2, py0+1.78, "Serial command protocol  (3 bytes)", ha="center",
        fontsize=10.5, fontweight="bold", color="#155e75")
ax.text(mx+mw/2, py0+1.42, "[ CMD ] [ ADDR ] [ DATA ]", ha="center",
        fontsize=11, family="monospace", fontweight="bold", color="#0f172a")
proto = [("0x01", "WRITE", "bus[ADDR] ← DATA"),
         ("0x02", "READ", "reply DATA = bus[ADDR] via TX"),
         ("0x03", "RUN", "write START → kick CGRA run")]
yy = py0+1.12
for cmd, nm, act in proto:
    ax.text(mx+0.32, yy, cmd, ha="left", va="center", fontsize=9.2,
            family="monospace", fontweight="bold", color=C["bridge"])
    ax.text(mx+1.05, yy, nm, ha="left", va="center", fontsize=9.2,
            fontweight="bold", color="#0f172a")
    ax.text(mx+2.15, yy, act, ha="left", va="center", fontsize=8.6, color="#334155")
    yy -= 0.34

fig.savefig("output/nanocgra_lite_3x3_opt/slides/arch_diagram.png", dpi=150,
            facecolor="white", bbox_inches="tight")
print("wrote arch_diagram.png")
