# Signoff Status — NanoCGRA_Lite 3x3 OPT D04

Date: 2026-08-29
Design: `output/nanocgra_lite_3x3_opt`
Top: `NanoCGRA_Lite`
Final layout: `gds/nanocgra_lite_3x3_opt_filled.gds`
Target slot/template: `D04`

## Results

| Item | Status | Evidence |
|---|---:|---|
| D04 block size | PASS | DEF die area is `1100000 × 1100000` DBU at 2000 DBU/µm = `550 µm × 550 µm`; GDS bbox is `550 µm × 550 µm`. |
| D04 pin geometry | PASS | DEF pin section reconciled to provided `D04_D.def` after 10× DBU scaling. |
| D04 wrapper interface | DONE | Top-level `NanoCGRA_Lite` exposes 21 D04-facing pins; original functional core is preserved as `NanoCGRA_Lite_core`. |
| Main DRC | PASS | `reports/signoff/drc_main_d04_summary.txt`: 0 violations. |
| Density | PASS | `reports/signoff/density_filled_d04_summary.txt`: 0 violations on the filled GDS. |
| Antenna | PASS | `reports/signoff/antenna_filled_d04_summary.txt`: 0 violations on the filled GDS. |
| LVS | PASS | `reports/lvs/netgen_final.log`: `Netlists match uniquely.` / `Result: Circuits match uniquely.` |
| P&R routing | PASS | `logs/pnr_d04.log`: 0 pin violations and 0 net violations. |

## Final LVS result

```text
Circuit 1 contains 5321 devices, Circuit 2 contains 5321 devices.
Circuit 1 contains 5339 nets,    Circuit 2 contains 5339 nets.
Netlists match uniquely.
Result: Circuits match uniquely.
```

## Notes

The latest update addresses the D04 audit feedback. The previous `466.555 µm × 466.555 µm` layout was replaced with a D04-sized `550 µm × 550 µm` implementation. The final GDS, filled GDS, DEF, pin geometry, labels, DRC, density, antenna, and LVS artifacts have all been regenerated for the D04 version.

The D04 wrapper preserves the original `_opt` functionality by mapping `clk`, `rst_n`, `uart_rx`, and core `uart_tx` to the D04-facing interface. Extra D04 pad-control pins are tied to fixed safe values.
