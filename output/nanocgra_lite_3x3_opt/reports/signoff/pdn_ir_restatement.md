# PDN / IR Restatement after LVS Closure & Metal Fill

Design: `nanocgra_lite_3x3_opt` (`NanoCGRA_Lite`)
Date: 2026-08-27

## Signoff Basis

The final signoff artifact is the metal-filled GDS:
`output/nanocgra_lite_3x3_opt/gds/nanocgra_lite_3x3_opt_filled.gds`

This layout includes electrically inert dummy metal fill on layers M2, M3, M4, and M5 to satisfy GF180 density requirements.

## LVS status

LVS has been closed clean on the routed netlist (`Netlists match uniquely`). The source netlist used for this verdict includes:
- Removal of the `uart_tx` internal alias/assign boundary (DFF Q now drives top-level port directly).
- Explicit PG pins for all APR-inserted buffer and clock-buffer cells.

Since the dummy fill is placed on dedicated dummy-purpose layers (e.g. 36/4, 42/4), the electrical connectivity remains identical to the non-filled layout which matched uniquely in `reports/lvs/netgen_final.log`.

## PDN connectivity statement

With LVS closed and density satisfied, the PDN connectivity is confirmed:
- VDD and VSS are the only top-level power rails.
- Standard-cell well/substrate pins are connected as expected: `VNW -> VDD`, `VPW -> VSS`.
- All repeaters and clock buffers carry valid logical and physical PG connections.

## Power / IR reference

Final post-route power estimate (consistent with LVS-matching netlist):
- Total power: 4.675 mW at 10 MHz, 5.0 V
- Internal: 3.813 mW
- Switching: 0.861 mW
- Leakage: 0.00113 mW
- Analytic current density is within bounds for the provided PDN stripes.
