# D04 LVS Status

Date: 2026-09-03  
Design: `output/nanocgra_lite_3x3_opt`  
Top: `NanoCGRA_Lite`

## Status

**PASS — real transistor-level LVS matches uniquely.**

`reports/lvs/netgen_final.log` reports:

```text
Circuit 1 contains 5362 devices, Circuit 2 contains 5362 devices.
Circuit 1 contains 5367 nets,    Circuit 2 contains 5367 nets.
Final result:
Circuits match uniquely.
NETGEN_LVS_PASSED
```

## LVS method

- Layout side: Magic 8.3.465 extracts the canonical unfilled GDS into
  `nanocgra_lite_3x3_opt_layout_lvs.spice`.
- `normalize_magic_devices.py` converts Magic's extracted GF180
  `X... nfet_05v0/pfet_05v0` proxy syntax to real MOS `M` records. It does not
  replace cells with empty stubs or derive the source view from layout.
- Source side: `verilog_to_lvs_spice.py` converts the populated powered
  post-route Verilog into hierarchical SPICE using official GF180 PDK CDL pin
  order.
- `run_lvs_final.tcl` compares these independent views with the official GF180
  Netgen setup and fails closed unless the comparison reports a unique match.

The former 5,321-device normalized-stub result is withdrawn and must not be
used. The current pass marker is `reports/lvs/netgen.complete`.
