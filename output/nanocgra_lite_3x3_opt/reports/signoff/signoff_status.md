# Signoff Status — NanoCGRA_Lite 3x3 OPT D04

Date: 2026-09-08
Top: `NanoCGRA_Lite`
Canonical layout: `gds/nanocgra_lite_3x3_opt.gds` (unfilled)
Reference contract: `pnr/D04.def` (550 µm × 550 µm, 21 Metal2 pins, geometry byte-for-byte equivalent to reviewer's `D04_D.def`)

## Current results

| Item | Status | Evidence |
|---|---|---|
| D04 size/top | PASS | Sole top `NanoCGRA_Lite`, 550.000 × 550.000 µm |
| D04 pin geometry vs reviewer's `D04_D.def` | PASS | All 21 pins in final `nanocgra_lite_3x3_opt.def` match the reviewer's authoritative pad-side coordinates (after ×10 unit scaling). Verified by direct set comparison. |
| Signal-pin M2 width/spacing | PASS | All signal pins ≥0.28 µm; router geometry preserved; detailed-route and full DRC clean |
| Generated-via integration | PASS | Flow-generated M2/M3/M4 landings are 0.28 × 0.52 µm = 0.1456 µm²; Via4 cuts remain 0.26 × 0.26 µm with legal spacing; no post-route geometry growth |
| Full GF180 DRC | PASS | All 53 official foundry variant-C (9K/5LM) rule-table reports have zero items |
| Standard-cell row fill | PASS | Reachable `fill_1/2/4/8/16`, `filltie`, and `endcap` cells |
| Project dummy-purpose fill | PASS | No shapes on 34/4, 36/4, 42/4, 46/4, 81/4, or 53/4 |
| D04 VDD/VSS boundary connection | PASS | 1.6 µm M4/M5 ring matches 1.6 µm internal straps; all 6 VDD and all 6 VSS Metal2 fingers have staged same-net via/route chains |
| CTS and detailed routing | PASS | `reports/flow.complete`; `reports/route_drc.rpt` is empty |
| Post-route STA | PASS at ss/125°C/4.5 V | WNS/TNS 0.00; setup slack 74.66 ns; hold slack 1.50 ns |
| Max slew/capacitance/fanout | No reported violators | `reports/signoff/sta_ss_repair.rpt` |
| PDNSim | COMPLETED, diagnostic assumptions | Default block-level checkerboard VSRC model; package-aware analysis remains top-level work |
| Magic GDS extraction | PASS | Magic 8.3.465; `reports/lvs/extraction.complete` |
| Real transistor-level LVS | PASS | Unique match: 5,362 devices and 5,367 nets on each side |

## Integration-review repair

- **D04 pin geometry re-alignment (2026-09-07)**: The reviewer resent a corrected `D04_D.def` on 2026-08-28 with slightly different signal-pin Y-coordinates and a full 1.0 µm shift for `uart_tx_IN`. `pnr/D04.def` matches those authoritative coordinates after ×10 unit scaling from 200 to 2000 DBU/µm, and the flow places and enforces all 21 pin rectangles directly while preserving router-generated signal routes.
- **Minimum-area/Via4 repair (2026-09-08)**: `build_drc_clean_tech_lef.py` generates the routing tech LEF before P&R. It keeps every foundry cut at 0.26 × 0.26 µm and preserves cut spacing, while extending only M2/M3/M4 via landings to 0.28 × 0.52 µm (0.1456 µm², above the 0.1444 µm² minimum). VDD fingers now terminate on existing PDN M4 stripes and reuse PDN-generated M4/M5 crossings, avoiding overlapping custom Via4 arrays.
- The generated PDN now uses a 1.6 µm M4/M5 VDD/VSS core ring matched to the 1.6 µm internal straps. All six D04 VDD fingers and all six D04 VSS fingers connect through staged same-net transitions without changing signal-pin placement.
- All 21 D04 pins are placed at the authoritative coordinates before routing and rechecked in the final DEF; the final GDS labels use the first physical rectangle of each multi-rectangle PG pin so LVS sees the connected pad finger.
- Generated DEF-via helper instances are flattened without changing their dimensions; legal landing area is already defined in the pre-route technical LEF.
- The submitted LVS config relies on the base config for standard-cell models and no longer duplicates the PDK CDL or includes unsupported script/log keys.
- Signoff now invokes the official GF180 DRC runner for variant C (9K/5LM), requires all 53 rule-table reports, and fails closed if any report contains an item.
- The canonical layout remains unfilled; density/antenna closure for the assembled chip remains the chip-top integration flow's responsibility.
- `uart_tx_IN` remains intentionally unused and is identically disconnected on both LVS sides.
