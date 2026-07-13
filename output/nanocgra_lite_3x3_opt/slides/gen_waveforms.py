#!/usr/bin/env python3
"""UART-protocol timing waveforms for NanoCGRA-Lite 3x3 OPT (4-pin UART-only).
   Stylized, presentation-grade digital-timing figure (matplotlib) matching the
   Chip Orchestra reference deck. Shows the 3-byte serial packet framing on
   uart_rx / uart_tx (start / 8 data LSB-first / stop) and the decoded internal
   MMIO-bus transactions for WRITE, READ+reply and RUN commands."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})

BITW = 1.0        # one UART baud period
GAP  = 2.0        # idle gap between bytes
HI, LO = 0.90, 0.10

def lane_label(ax, y, label):
    ax.text(-1.4, y+0.5, label, ha="right", va="center", fontsize=10.5,
            family="monospace", fontweight="bold")

def draw_serial(ax, y, x0, bytes_labels, color, annotate_first=True):
    """Draw a UART serial line: idle-high, start(0), 8 data LSB-first, stop(1)."""
    xs, ys = [x0-1.0], [y+HI]      # idle high lead-in
    x = x0
    marks = []
    for bi, (b, lab) in enumerate(bytes_labels):
        b_start = x
        levels = [0] + [(b >> k) & 1 for k in range(8)] + [1]   # start, d0..d7, stop
        for lv in levels:
            h = y + (HI if lv else LO)
            xs.append(x); ys.append(h)
            x += BITW
            xs.append(x); ys.append(h)
        marks.append((b_start, x, lab, b))
        # idle gap high
        xs.append(x); ys.append(y+HI)
        x += GAP
        xs.append(x); ys.append(y+HI)
    ax.plot(xs, ys, color=color, lw=1.8, solid_joinstyle="miter")
    # byte brackets + labels
    for (bs, be, lab, b) in marks:
        ax.annotate("", xy=(be, y+1.06), xytext=(bs, y+1.06),
                    arrowprops=dict(arrowstyle="|-|", color="#64748b", lw=1.0))
        ax.text((bs+be)/2, y+1.20, lab, ha="center", va="bottom",
                fontsize=8.2, color="#334155", fontweight="bold")
    if annotate_first and marks:
        bs = marks[0][0]
        ax.text(bs+0.5, y-0.14, "start", ha="center", va="top", fontsize=6.8,
                color="#94a3b8", style="italic")
        ax.text(bs+9.5, y-0.14, "stop", ha="center", va="top", fontsize=6.8,
                color="#94a3b8", style="italic")
    return x

def draw_level(ax, y, color, segs):
    """segs: list of (x0,x1,level 0/1). Draw a digital control line."""
    xs, ys = [], []
    for (x0, x1, lv) in segs:
        h = y + (HI if lv else LO)
        xs += [x0, x1]; ys += [h, h]
    ax.plot(xs, ys, color=color, lw=1.8, drawstyle="steps-post", solid_joinstyle="miter")

def draw_bus(ax, y, color, segs):
    """segs: list of (x0,x1,text or None). None = unknown (X)."""
    for (x0, x1, txt) in segs:
        if x1 <= x0:
            continue
        unknown = txt is None
        fc = "#e8ecf4" if not unknown else "#f6d6d6"
        s = min((x1-x0)*0.10, 0.5)
        pts = [(x0+s, y+LO), (x1-s, y+LO), (x1, y+0.5),
               (x1-s, y+HI), (x0+s, y+HI), (x0, y+0.5)]
        ax.add_patch(Polygon(pts, closed=True, facecolor=fc, edgecolor=color, lw=1.4))
        if not unknown:
            ax.text((x0+x1)/2, y+0.5, txt, ha="center", va="center",
                    fontsize=8.6, family="monospace")

fig = plt.figure(figsize=(15, 12))
fig.suptitle("NanoCGRA-Lite 3×3 OPT  —  UART-Only Protocol Waveforms (serial packet + MMIO bus)",
             fontsize=16.5, fontweight="bold", y=0.985)
gs = fig.add_gridspec(3, 1, hspace=0.42, top=0.93, bottom=0.055, left=0.12, right=0.975)

# ---------------- Panel 1 : WRITE ----------------
BLUE = "#1f6feb"
ax1 = fig.add_subplot(gs[0])
x0 = 2.0
pkt_end = draw_serial(ax1, 4*1.25, x0, [(0x01, "CMD=0x01 WRITE"),
                                        (0x05, "ADDR=0x05"),
                                        (0x7B, "DATA=0x7B")], BLUE)
lane_label(ax1, 4*1.25, "uart_rx")
# decoded MMIO write after packet
we_x = pkt_end + 1.0
lane_label(ax1, 3*1.25, "bus_we")
draw_level(ax1, 3*1.25, BLUE, [(x0-1, we_x, 0), (we_x, we_x+2, 1), (we_x+2, we_x+6, 0)])
lane_label(ax1, 2*1.25, "bus_addr")
draw_bus(ax1, 2*1.25, BLUE, [(x0-1, we_x, None), (we_x, we_x+6, "0x05")])
lane_label(ax1, 1*1.25, "bus_wdata")
draw_bus(ax1, 1*1.25, BLUE, [(x0-1, we_x, None), (we_x, we_x+6, "0x7B")])
lane_label(ax1, 0*1.25, "SRAM[5]")
draw_bus(ax1, 0*1.25, BLUE, [(x0-1, we_x+2, None), (we_x+2, we_x+6, "0x7B (=123)")])
ax1.set_title("WRITE command  —  host → chip:  [01][05][7B]  ⇒  bus[0x05] ← 0x7B  (SRAM store)",
              fontsize=12, fontweight="bold", loc="left", color=BLUE, pad=18)
xmax1 = we_x+7

# ---------------- Panel 2 : READ + TX reply ----------------
GREEN = "#1a7f37"
ax2 = fig.add_subplot(gs[1])
rp_end = draw_serial(ax2, 4*1.25, x0, [(0x02, "CMD=0x02 READ"),
                                       (0x05, "ADDR=0x05")], GREEN)
lane_label(ax2, 4*1.25, "uart_rx")
re_x = rp_end + 1.0
lane_label(ax2, 3*1.25, "bus_re")
draw_level(ax2, 3*1.25, GREEN, [(x0-1, re_x, 0), (re_x, re_x+2, 1), (re_x+2, re_x+16, 0)])
lane_label(ax2, 2*1.25, "bus_rdata")
draw_bus(ax2, 2*1.25, GREEN, [(x0-1, re_x+2, None), (re_x+2, re_x+16, "0x7B")])
tx_x = re_x + 4
tx_end = draw_serial(ax2, 1*1.25, tx_x, [(0x7B, "TX reply = 0x7B")], GREEN, annotate_first=True)
lane_label(ax2, 1*1.25, "uart_tx")
lane_label(ax2, 0*1.25, "host RX")
draw_bus(ax2, 0*1.25, GREEN, [(x0-1, tx_end-1, None), (tx_end-1, tx_end+3, "0x7B (=123)")])
ax2.set_title("READ command  —  [02][05]  ⇒  bus[0x05] read = 0x7B  ⇒  serialized back on uart_tx",
              fontsize=12, fontweight="bold", loc="left", color=GREEN, pad=18)
xmax2 = tx_end+4

# ---------------- Panel 3 : RUN ----------------
PURP = "#8250df"
ax3 = fig.add_subplot(gs[2])
run_end = draw_serial(ax3, 4*1.25, x0, [(0x03, "CMD=0x03 RUN"),
                                        (0xA0, "ADDR=0xA0 START"),
                                        (0x01, "DATA=0x01")], PURP)
lane_label(ax3, 4*1.25, "uart_rx")
sp_x = run_end + 1.0
lane_label(ax3, 3*1.25, "start_pulse")
draw_level(ax3, 3*1.25, PURP, [(x0-1, sp_x, 0), (sp_x, sp_x+1, 1), (sp_x+1, sp_x+18, 0)])
lane_label(ax3, 2*1.25, "busy")
draw_level(ax3, 2*1.25, PURP, [(x0-1, sp_x+1, 0), (sp_x+1, sp_x+15, 1), (sp_x+15, sp_x+18, 0)])
lane_label(ax3, 1*1.25, "done")
draw_level(ax3, 1*1.25, PURP, [(x0-1, sp_x+15, 0), (sp_x+15, sp_x+18, 1)])
lane_label(ax3, 0*1.25, "cgra_result")
draw_bus(ax3, 0*1.25, PURP, [(x0-1, sp_x+15, None), (sp_x+15, sp_x+18, "0x08 (ADD 5+3)")])
ax3.set_title("RUN command  —  [03][A0][01]  ⇒  START strobe  ⇒  Nano Controller drives CGRA (result = 8)",
              fontsize=12, fontweight="bold", loc="left", color=PURP, pad=18)
xmax3 = sp_x+19

for ax, xmax in [(ax1, xmax1), (ax2, xmax2), (ax3, xmax3)]:
    ax.set_xlim(-3.0, xmax)
    ax.set_ylim(-0.45, 5*1.25)
    ax.set_yticks([])
    for sp in ["top", "right", "left"]:
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#999999")
    ax.set_xlabel("UART bit-stream  (1 bit = 1 baud period = 87 clk @ 10 MHz);  MMIO-bus events shown after packet decode",
                  fontsize=9, color="#555555")
    ax.grid(axis="x", ls=":", color="#cccccc", alpha=0.55)

fig.savefig("output/nanocgra_lite_3x3_opt/slides/simulation_waveforms.png", dpi=150,
            facecolor="white", bbox_inches="tight")
print("wrote simulation_waveforms.png")
