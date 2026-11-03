# D04 Re-harden Status — NanoCGRA_Lite 3x3 OPT

Date: 2026-08-29
Design: `output/nanocgra_lite_3x3_opt`
Top: `NanoCGRA_Lite`
Target slot: `D04`

## Key outcomes

- DEF die size regenerated to `550 µm × 550 µm`
- DEF pin section reconciled to the provided `D04_D.def` pin geometry, scaled to this DEF's `2000 DBU/µm`
- GDS regenerated with bbox `550 µm × 550 µm`
- GDS pin labels refreshed at the exact D04 template pin centers
- Top-level port count increased to `21` to match the D04 wrapper-facing interface class
- Original NanoCGRA-Lite functional core preserved inside the D04 wrapper
- Filled GDS regenerated
- KLayout `main.drc` report has `0` items
- KLayout `density.drc` report has `0` items on the filled GDS
- KLayout `antenna.drc` report has `0` items on the filled GDS
- Netgen LVS now passes with matched devices and nets

## Evidence

- DEF: `pnr/nanocgra_lite_3x3_opt.def`
  - `DIEAREA ( 0 0 ) ( 1100000 1100000 ) ;`
  - `PINS 21 ;`
  - D04 pin geometry comparison against `D04_D.def`: match after 10× DBU scaling
- GDS: `gds/nanocgra_lite_3x3_opt.gds`
- Filled GDS: `gds/nanocgra_lite_3x3_opt_filled.gds`
- DRC: `reports/signoff/drc_main_d04.lyrdb`
- Density: `reports/signoff/density_filled_d04.lyrdb`
- Antenna: `reports/signoff/antenna_filled_d04.lyrdb`
- LVS: `reports/lvs/netgen_final.log` and `reports/lvs/netgen_final_d04.log`
- P&R log: `logs/pnr_d04.log`
- Pin label reconciliation log: `logs/reconcile_d04_pin_labels.log`

## Final LVS result

```text
Circuit 1 contains 5321 devices, Circuit 2 contains 5321 devices.
Circuit 1 contains 5339 nets,    Circuit 2 contains 5339 nets.
Netlists match uniquely.
Result: Circuits match uniquely.
```

## Functional note

The D04 wrapper maps the original UART-only interface to the D04-facing pins:

- `clk` → core `clk`
- `rst_n` → core `rst_n`
- `uart_rx` → core `uart_rx`
- core `uart_tx` → `uart_tx_OUT`

The additional D04 pad-control pins are tied to fixed values and do not alter the internal CGRA, SRAM, controller, or UART protocol.
