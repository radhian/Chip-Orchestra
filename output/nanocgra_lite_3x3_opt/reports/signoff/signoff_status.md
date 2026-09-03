# Signoff Status — NanoCGRA_Lite 3x3 OPT D04

Date: 2026-09-03  
Top: `NanoCGRA_Lite`  
Canonical layout: `gds/nanocgra_lite_3x3_opt.gds` (unfilled)  
Reference contract: `pnr/D04.def` (550 µm × 550 µm, 21 Metal2 pins)

## Current results

| Item | Status | Evidence |
|---|---|---|
| D04 size/top | PASS | Canonical GDS audit: sole top `NanoCGRA_Lite`, 550.000 × 550.000 µm |
| Standard-cell row fill | PASS | Reachable `fill_1/2/4/8/16`, `filltie`, and `endcap` cells |
| Project dummy-purpose fill | PASS | No shapes on 34/4, 36/4, 42/4, 46/4, 81/4, or 53/4 |
| UART boundary-pin spacing | PASS | `reports/route_drc.rpt` is empty after documented OE/OUT/SL corrections |
| D04 VDD/VSS boundary connection | PASS at DEF topology level | Explicit M2-M3-M4 routes and via stacks; `pnr/check_d04_pg.py` |
| CTS and detailed routing | PASS | `reports/flow.complete`, `logs/pnr_repair.log` |
| Post-route STA | PASS at ss/125°C/4.5 V | WNS/TNS 0.00; setup slack 75.17 ns; hold slack 1.50 ns |
| Max slew/capacitance/fanout | No reported violators | `reports/signoff/sta_ss_repair.rpt` |
| Internal PDN connectivity | PASS | All VDD and VSS stripes connected |
| PDNSim | COMPLETED, diagnostic assumptions | Worst reported drop ≈1.55 µV with default checkerboard VSRC placement |
| Main KLayout DRC | PASS | `reports/signoff/drc_main_repair.lyrdb` contains zero items |
| Magic GDS extraction | PASS | Magic 8.3.465; `reports/lvs/extraction.complete` |
| Real transistor-level LVS | PASS | Unique match: 5,362 devices and 5,367 nets on each side; `reports/lvs/netgen_final.log` |
| Density/antenna integration signoff | Pending chip integration | No project-level dummy fill; chip-top flow owns final density/antenna closure |

## Method and limitations

- The former normalized empty-stub result is withdrawn and is not used.
- Layout LVS starts from the canonical GDS extracted by Magic. Magic's GF180 MOS proxy records are converted to real MOS records without changing extracted nets or geometry.
- Source LVS starts independently from the populated powered post-route Verilog, with cell pin order taken from the official GF180 PDK CDL.
- Netgen writes `reports/lvs/netgen.complete` only after a unique match; otherwise the runner exits non-zero.
- Both matched views report one disconnected top-level pin, corresponding to the intentionally unused `uart_tx_IN` interface in this configuration.
- The original D04 DEF contains illegal Metal2 spacing in the UART cluster. The generated DEF minimally moves `uart_tx_OE`, `uart_tx_OUT`, and `uart_tx_SL`; all other D04 pin geometry is preserved.
- PDNSim used default checkerboard voltage sources because package-specific source/current data was not supplied. Treat its values as diagnostic, not package-aware final IR signoff.
