# Signoff Status — NanoCGRA_Lite 3x3 OPT

Date: 2026-08-27
Design: `output/nanocgra_lite_3x3_opt`
Top: `NanoCGRA_Lite`
Final layout: `gds/nanocgra_lite_3x3_opt_filled.gds`

## Results

| Item | Status | Evidence |
|---|---:|---|
| LVS final verdict | PASS | `reports/lvs/netgen_final.log`: `Netlists match uniquely.` / `Result: Circuits match uniquely.` |
| `uart_tx` boundary mismatch | FIXED | `_9651_/Q` now drives top-level `uart_tx` directly; intermediate `assign uart_tx = \u_uart.uart_tx` removed. |
| Missing PG pins on APR buffers | FIXED | All `buf_*` / `clkbuf_*` cells in the routed power netlists now have `.VDD/.VNW/.VPW/.VSS`. |
| Dummy fill insertion | DONE | `gds/nanocgra_lite_3x3_opt_filled.gds`; `reports/signoff/fill.log` shows 8,012 dummy fill rectangles inserted on M2/M3/M4/M5 dummy-purpose layers. |
| Filled antenna | PASS | `reports/signoff/antenna_filled.lyrdb` has 0 violation items; see `reports/signoff/antenna_filled_summary.txt`. |
| Filled density | PASS | `reports/signoff/density_filled.lyrdb` has 0 violation items; see `reports/signoff/density_filled_summary.txt`. |
| Filled-GDS LVS extraction | TOOL-BLOCKED | `reports/lvs/extract_filled_gds.tcl` was added, but Magic GDS extraction segfaults in this container before netlist generation; see `reports/lvs/magic_extract_filled_gds.log` and `reports/lvs/filled_lvs_status.md`. |
| PDN/IR restatement | DONE | `reports/signoff/pdn_ir_restatement.md`. |
| SS STA | PASS | `reports/signoff/sta_ss.txt`: setup WNS +73.90 ns, hold WNS +1.53 ns. |
| FF STA | PASS | `reports/signoff/sta_ff.txt`: setup WNS +77.96 ns, hold WNS +0.50 ns. |

## Notes

The original pre-fill GDS density run is retained as `reports/signoff/density_summary.txt` and shows the previous blocker. The final filled GDS closes the density deck with 0 violations.

The added fill is on GF180 dummy-purpose metal layers only:

- M2 dummy: `36/4`
- M3 dummy: `42/4`
- M4 dummy: `46/4`
- M5 dummy: `81/4`

Because these layers are non-functional dummy fill, the electrical netlist is unchanged from the LVS-clean routed layout. A literal filled-GDS LVS rerun should be possible with a Magic version compatible with the installed GF180 techfile (`>= 8.3.411`); the current environment has Magic `8.3.105` and crashes on GDS extraction.
