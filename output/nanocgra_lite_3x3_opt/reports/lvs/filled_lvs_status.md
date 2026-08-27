# Filled-GDS LVS Status — NanoCGRA_Lite 3x3 OPT

Date: 2026-08-27
Design: `output/nanocgra_lite_3x3_opt`
Top: `NanoCGRA_Lite`
Filled layout: `gds/nanocgra_lite_3x3_opt_filled.gds`

## Verdict

Formal Netgen LVS remains closed on the routed physical netlist:

- `reports/lvs/netgen_final.log`
- `Netlists match uniquely.`
- `Result: Circuits match uniquely.`
- Final comparison: 5325 devices / 5330 nets on both sides.

The filled GDS contains only density fill on GF180 dummy-purpose layers:

- M2 dummy: `36/4`
- M3 dummy: `42/4`
- M4 dummy: `46/4`
- M5 dummy: `81/4`

These layers are included by the GF180 density deck and are treated as non-functional dummy fill, so they do not change the electrical netlist relative to the LVS-clean routed layout.

## Filled GDS extraction attempt

A Magic GDS extraction script was added at:

- `reports/lvs/extract_filled_gds.tcl`

The run failed in this environment with Magic exit code 139 before producing a SPICE netlist:

- `reports/lvs/magic_extract_filled_gds.log`

The same Magic/GDS extraction path also crashes on the original non-filled GDS, which points to an environment/tooling issue rather than an introduced connectivity issue. The log shows the installed Magic is older than required by the GF180 techfile:

- installed Magic: `8.3.105`
- GF180 techfile requires: `8.3.411`

## Practical signoff position

For this repository snapshot, the evidence chain is:

1. The routed design LVS passes uniquely through the working DEF-based Magic extraction + Netgen flow.
2. The filled GDS differs only by dummy-purpose metal fill rectangles.
3. Filled density passes with 0 violations.
4. Filled antenna passes with 0 violations.

If the reviewer requires a literal filled-GDS LVS rerun, it should be rerun with Magic `>= 8.3.411` or another GF180-compatible GDS extractor. In the current container, filled-GDS LVS cannot be completed because Magic GDS extraction segfaults before netlist generation.
