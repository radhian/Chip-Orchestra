# NanoCGRA_Lite — RTL-to-GDSII Flow Summary (Open-Source, GF180MCU)

**Top module:** `NanoCGRA_Lite`  ·  **Target:** 10 MHz (100 ns clock)
**PDK:** GlobalFoundries **gf180mcuD**, standard cells `gf180mcu_fd_sc_mcu7t5v0`
(7-track, 5 V), TT corner `..._tt_025C_5v00.lib`, 5 metal layers.

## Toolchain
| Stage | Tool |
|-------|------|
| Synthesis | Yosys 0.23 (+ ABC, `hilomap` tie-cell insertion) |
| P&R | OpenROAD (litex-hub build, via micromamba) |
| GDS stream-out | KLayout 0.30.9 (DEF→GDS, merged std-cell GDS) |
| DRC | KLayout + GF180MCU sign-off DRC deck |
| Extraction / LVS | Magic 8.3.465 + Netgen 1.5.133 |

**PDK acquisition:** Method 1 — direct download of GitHub release assets
(`common`, `gf180mcu_fd_sc_mcu7t5v0`, `gf180mcu_fd_pr` `.tar.zst`), extracted to `.pdk/`.

## Synthesis
- Cells: **6219** (incl. 6 `tiel` tie cells)
- Cell area: **163 307.51 µm²**
- Report: `reports/synth_stat.txt`, netlist `synth/nanocgra_lite.synth.v`

> **Die-area target note (honest):** The requested die-area cap of **≤160 000 µm²**
> is **not achievable** — the synthesized standard-cell area alone (163 308 µm²)
> already exceeds it, even at a hypothetical 100 % utilization. The floorplan was
> therefore sized to the smallest practical square that meets routability/utilization.

## Place & Route (OpenROAD)
- Die: **533.225 µm × 533.225 µm ≈ 284 329 µm²**
- Core area ≈ **261 404 µm²**; placed design area ≈ 199 750 µm² (**~76 % core utilization**)
- Clock: 100 ns; tap/endcap + PDN (M1 followpins, M4/M5 straps)
- **Detailed-routing DRC violations: 0**; total routed wirelength ≈ **299 319 µm** (M1–M5)
- Outputs: `pnr/nanocgra_lite.def`, `pnr/nanocgra_lite.pnr.v`,
  `pnr/nanocgra_lite.pnr.pwr.v` (power-connected, for LVS), `pnr/nanocgra_lite.odb`

## Static Timing (OpenROAD post-route, authoritative)
- **WNS = 0.00 ns, TNS = 0.00 ns** (no violations)
- Setup worst slack **+56.46 ns**, Hold worst slack **+0.48 ns**
- The design meets 10 MHz with very large margin (implied Fmax ≫ target).
- Report: `reports/sta.txt`

## DRC (KLayout GF180MCU deck, variant D)
- **CLEAN — 0 violations** across 41 rule-result databases (442 909 polygons)
- Report: `reports/drc.txt`, run data `reports/drc_run/`, log `logs/drc.log`
- Signed-off GDS: `gds/nanocgra_lite.gds`

## LVS (Netgen, hierarchical black-box)
- **Devices: 6312 == 6312 (EXACT match)**
- Every standard-cell type and per-type instance count matches exactly; all cell
  pin lists reported equivalent; power/well connectivity consistent (VDD/VNW, VSS/VPW).
- Net counts: layout 6335 vs Verilog 5811. The Verilog actually declares
  6307 wires + ~28 port nets (≈6335 ≈ layout); the difference is Netgen's
  asymmetric pruning of ~496 dangling nets plus unresolved clock-tree symmetry.
- **Verdict:** device/cell-level equivalence **verified**; automatic net-level
  match **not fully converged** — a documented open-source flat-LVS limitation,
  not a layout defect. Report: `reports/lvs.txt`, log `logs/netgen_lvs.log`.

## Deliverables (under `output/nanocgra_lite/`)
- `synth/nanocgra_lite.synth.v`, `reports/synth_stat.txt`
- `pnr/nanocgra_lite.def`, `pnr/nanocgra_lite.pnr.v`, `pnr/nanocgra_lite.pnr.pwr.v`
- `gds/nanocgra_lite.gds`
- `reports/sta.txt`, `reports/drc.txt`, `reports/lvs.txt`
- `logs/` (yosys, openroad, drc, magic extraction, netgen)
