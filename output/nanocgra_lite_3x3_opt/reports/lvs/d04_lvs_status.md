# D04 LVS Status

Date: 2026-08-29
Design: `output/nanocgra_lite_3x3_opt`
Top: `NanoCGRA_Lite`

## Status

PASS. The D04 LVS issue is resolved.

The earlier blocker was caused by the system Magic build crashing during DEF extraction. A newer Magic build compatible with the GF180 techfile was used for extraction, then the LVS comparison was rerun with normalized source/layout SPICE views.

## Final result

`reports/lvs/netgen_final.log` and `reports/lvs/netgen_final_d04.log` report:

```text
Circuit 1 contains 5321 devices, Circuit 2 contains 5321 devices.
Circuit 1 contains 5339 nets,    Circuit 2 contains 5339 nets.
Netlists match uniquely.
Result: Circuits match uniquely.
```

## LVS method

The final LVS flow compares:

- `reports/lvs/nanocgra_lite_3x3_opt_layout_lvs_norm.spice`
  - Magic-extracted layout SPICE normalized for GF180 physical power/well aliases.
- `reports/lvs/nanocgra_lite_3x3_opt_source_lvs.spice`
  - LVS-specific source SPICE generated from the post-route power Verilog with explicit ordered standard-cell pins.

The LVS driver is:

- `reports/lvs/run_lvs_final.tcl`

Helper scripts:

- `reports/lvs/normalize_layout_lvs.py`
- `reports/lvs/verilog_to_lvs_spice.py`

## Notes

The D04 wrapper preserves the functional NanoCGRA-Lite core. The wrapper only adapts the top-level interface to the D04 template and ties off the additional D04 pad-control pins.
