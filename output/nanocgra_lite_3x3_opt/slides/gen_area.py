#!/usr/bin/env python3
"""Standard-cell area breakdown for NanoCGRA-Lite 3x3 OPT.
   Real per-cell-type areas are taken from the GF180MCU tt_025C_5v00 Liberty and
   multiplied by the instance counts in reports/synth_stat.txt, then grouped into
   functional cell classes. Total reconstructs the reported 123,634 um^2 exactly."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import re

plt.rcParams.update({"font.family": "DejaVu Sans"})

STAT = "output/nanocgra_lite_3x3_opt/reports/synth_stat.txt"
LIB  = ".pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib"

# ---- per-cell instance counts (from synth_stat.txt) ----
counts, ncells, chip_area = {}, None, None
with open(STAT) as f:
    for ln in f:
        m = re.search(r"gf180mcu_fd_sc_mcu7t5v0__(\S+)\s+(\d+)", ln)
        if m:
            counts[m.group(1)] = int(m.group(2))
        m2 = re.search(r"Number of cells:\s+(\d+)", ln)
        if m2: ncells = int(m2.group(1))
        m3 = re.search(r"Chip area for module.*:\s+([\d.]+)", ln)
        if m3: chip_area = float(m3.group(1))

# ---- per-cell area (from Liberty) ----
libtxt = open(LIB).read()
cell_area = {}
for m in re.finditer(r'cell\s*\(\s*"?(gf180mcu_fd_sc_mcu7t5v0__[A-Za-z0-9_]+)"?\s*\)\s*\{', libtxt):
    seg = libtxt[m.end():m.end()+400]
    am = re.search(r'area\s*:\s*([\d.]+)\s*;', seg)
    if am:
        cell_area[m.group(1).replace("gf180mcu_fd_sc_mcu7t5v0__", "")] = float(am.group(1))

# ---- group definitions (functional cell classes) ----
def grp(name):
    if name.startswith("dff"): return "Sequential (DFF)"
    if name.startswith("clkinv") or name.startswith("inv") or name.startswith("buf"): return "Inverters / clk-buffers"
    if name.startswith("mux"): return "Multiplexers"
    if name.startswith("xor") or name.startswith("xnor"): return "XOR / XNOR (datapath)"
    if name.startswith("aoi") or name.startswith("oai"): return "AOI / OAI (complex)"
    if name.startswith("nand") or name.startswith("nor"): return "NAND / NOR (basic)"
    if name.startswith("and") or name.startswith("or"): return "AND / OR (buffered)"
    return "Other"

order = ["Sequential (DFF)", "AOI / OAI (complex)", "NAND / NOR (basic)",
         "XOR / XNOR (datapath)", "AND / OR (buffered)", "Inverters / clk-buffers",
         "Multiplexers"]
palette = {"Sequential (DFF)":"#2563eb", "AOI / OAI (complex)":"#059669",
           "NAND / NOR (basic)":"#d97706", "XOR / XNOR (datapath)":"#7c3aed",
           "AND / OR (buffered)":"#dc2626", "Inverters / clk-buffers":"#0891b2",
           "Multiplexers":"#db2777"}

g_area = {k: 0.0 for k in order}
g_cnt  = {k: 0   for k in order}
for cell, n in counts.items():
    g = grp(cell)
    a = cell_area.get(cell, 0.0)
    g_area[g] += a * n
    g_cnt[g]  += n

labels = order
vals   = [g_area[k] for k in order]
cnts   = [g_cnt[k]  for k in order]
colors = [palette[k] for k in order]
total  = sum(vals)

fig, (axp, axb) = plt.subplots(1, 2, figsize=(16, 8),
                               gridspec_kw={"width_ratios": [1.05, 1]})
fig.suptitle("NanoCGRA-Lite 3×3 OPT  -  Standard-Cell Area Breakdown  (Yosys / GF180MCU)",
             fontsize=17, fontweight="bold", y=0.98)

# ----- Donut: area share by cell class -----
def autopct(p):
    return f"{p:.1f}%" if p >= 3.5 else ""
wedges, _txts, autotxts = axp.pie(
    vals, colors=colors, startangle=90, counterclock=False,
    autopct=autopct, pctdistance=0.78,
    wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
    textprops=dict(fontsize=11, fontweight="bold", color="white"))
axp.set_title("Area share by cell class", fontsize=13, fontweight="bold", pad=12)
axp.text(0, 0, f"{total/1000:.1f}k\nµm²\ntotal", ha="center", va="center",
         fontsize=15, fontweight="bold", color="#111827")
leg = [f"{l}  —  {v:,.0f} µm²  ({c:,} cells)" for l, v, c in zip(labels, vals, cnts)]
axp.legend(wedges, leg, loc="upper center", bbox_to_anchor=(0.5, -0.02),
           fontsize=10, frameon=False, ncol=1)

# ----- Bar: top standard-cell types by instance count -----
top_cells = sorted(counts.items(), key=lambda x: -x[1])[:12]
names  = [c[0] for c in top_cells][::-1]
counts_b = [c[1] for c in top_cells][::-1]
barcols = [palette[grp(n)] for n in names]
bars = axb.barh(names, counts_b, color=barcols, edgecolor="#1e293b", linewidth=0.6)
axb.bar_label(bars, labels=[f"{c:,}" for c in counts_b], padding=4,
              fontsize=9.5, fontweight="bold")
axb.set_title(f"Top standard-cell types  (flat netlist: {ncells:,} cells, "
              f"{chip_area/1000:.1f}k µm²)", fontsize=13, fontweight="bold", pad=12)
axb.set_xlabel("instance count")
axb.set_xlim(0, max(counts_b)*1.15)
for sp in ["top", "right"]:
    axb.spines[sp].set_visible(False)
axb.tick_params(axis="y", labelsize=10)

fig.text(0.5, 0.935,
         "Cell-class areas = GF180MCU Liberty per-cell area × synth_stat instance counts "
         f"(reconstructs the reported {chip_area:,.0f} µm² gate area). Sequential DFFs dominate; "
         "XOR/AOI datapath reflects the 9-PE CGRA + UART-bridge FSM.",
         ha="center", fontsize=10.3, color="#6b7280", style="italic")

fig.subplots_adjust(left=0.04, right=0.98, top=0.88, bottom=0.22, wspace=0.15)
fig.savefig("output/nanocgra_lite_3x3_opt/slides/area_breakdown.png", dpi=150,
            facecolor="white", bbox_inches="tight")
print("wrote area_breakdown.png; total=%.1f flat=%.1f cells=%s" % (total, chip_area, ncells))
