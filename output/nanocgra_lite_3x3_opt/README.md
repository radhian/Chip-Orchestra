# NanoCGRA-Lite 3×3 + 32B — D04 tapeout repair package

This directory contains the GF180MCU implementation sources, generated artifacts,
and reproducible checks for the `NanoCGRA_Lite` D04 block. The D04 physical
contract is a **550 µm × 550 µm** die with 21 Metal2 boundary pins based on
`pnr/D04.def`.

## Current status (2026-09-03)

The repaired flow has been rerun end-to-end with OpenROAD, KLayout, Magic
8.3.465, and Netgen 1.5.272. The canonical GDS contains CTS and routed logic,
`fill_1/2/4/8/16` row fillers, `filltie`, and `endcap`, with no project-level
dummy-purpose fill. Explicit M2-M3-M4 routes connect the D04 `vdd` and `vss`
boundary pins to the internal PDN.

Fresh checks completed:

- Detailed-route DRC: PASS, zero violations.
- Main KLayout DRC: PASS, zero report items.
- Canonical GDS audit: PASS, sole `NanoCGRA_Lite` top, 550.000 × 550.000 µm.
- Real transistor-level LVS: PASS, unique match; 5,362 devices and 5,367 nets on both sides.
- Post-route STA at ss/125°C/4.5 V: WNS/TNS 0.00, setup slack 75.17 ns, hold slack 1.50 ns, with no reported max slew/capacitance/fanout violators.
- Internal PG connectivity: PASS; OpenROAD reports all VDD and VSS stripes connected.
- PDNSim: completed for VDD/VSS. Worst reported drop is approximately 1.55 µV under default checkerboard source assumptions; this is diagnostic rather than package-aware final IR signoff.

The supplied D04 reference has illegal Metal2 spacing in the UART pin cluster.
The generated DEF applies minimal documented spacing corrections to
`uart_tx_OE`, `uart_tx_OUT`, and `uart_tx_SL`, while preserving the D04 side,
layer, ordering, net names, die size, and all other pin geometry.

## Canonical flow

1. Synthesis produces `synth/nanocgra_lite_3x3_opt.synth.v`.
2. `pnr/flow.tcl` performs the fixed D04 floorplan, tap/endcap insertion, PDN,
   placement, CTS, timing repair, global/detailed routing, approved row-filler
   insertion, PG checks, electrical reports, and DEF/ODB/netlist generation.
3. `pnr/apply_d04_pin_contract.py` applies the D04 boundary contract plus the
   three documented UART Metal2 spacing corrections.
4. DEF-to-GDS conversion writes the **unfilled** canonical layout:
   `gds/nanocgra_lite_3x3_opt.gds`.
5. `reports/lvs/extract_gds.tcl` extracts the canonical GDS with compatible
   Magic and normalizes Magic's GF180 MOS proxy syntax into MOS device records
   without changing extracted geometry or connectivity.
6. `reports/lvs/verilog_to_lvs_spice.py` converts the populated powered
   post-route Verilog to source SPICE using official GF180 PDK CDL pin order.
7. `reports/lvs/run_lvs_final.tcl` compares the extracted layout and independent
   source views with the official PDK setup. It fails closed unless Netgen
   reports a unique match.
8. `reports/pdnsim_ir.tcl` produces VDD/VSS diagnostic PDNSim reports.
9. `validate.sh` checks config paths, GDS top/size, forbidden dummy layers,
   physical fillers, D04 PG topology, empty route-DRC output, required reports,
   and fresh completion/pass markers.

The prior normalized empty-stub LVS result and legacy `_filled.gds` are not
valid signoff evidence and must not be used. `gds/add_density_fill.py` is
intentionally fail-fast because chip-level integration owns density fill.

## Reproduction

Run from any directory without embedding checkout-specific paths:

```sh
export UPRJ_ROOT=/path/to/Chip-Orchestra
export PDK_ROOT=/path/to/pdks
export OPENROAD_BIN=/path/to/openroad
export MAGIC_BIN=/path/to/magic       # must be >= 8.3.411
export NETGEN_BIN=/path/to/netgen

"$UPRJ_ROOT/output/nanocgra_lite_3x3_opt/scripts/run_repair_signoff.sh"
```

The runner fails closed on non-zero main DRC or LVS mismatch. Final validation
also rejects a non-empty detailed-route DRC report.

## Integration note

Density/antenna closure against the assembled chip remains the responsibility
of the chip-top integration flow. Package-aware IR signoff should be rerun when
actual pad/bump locations and current assumptions are available.
