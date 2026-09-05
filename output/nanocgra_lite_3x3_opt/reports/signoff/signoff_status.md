# Signoff Status — NanoCGRA_Lite 3x3 OPT D04

Date: 2026-09-05
Top: `NanoCGRA_Lite`
Canonical layout: `gds/nanocgra_lite_3x3_opt.gds` (unfilled)
Reference contract: `pnr/D04.def` (550 µm × 550 µm, 21 Metal2 pins)

## Current results

| Item | Status | Evidence |
|---|---|---|
| D04 size/top | PASS | Sole top `NanoCGRA_Lite`, 550.000 × 550.000 µm |
| Signal-pin M2 width/spacing | PASS | All signal pins ≥0.28 µm; router geometry preserved; detailed-route and full DRC clean |
| Generated-via minimum area | PASS | All 18 M1–M5 landing shapes in reachable `VIA_*` cells ≥0.1444 µm² |
| Full GF180 DRC | PASS | Zero items in flat and deep modes with FEOL, BEOL, and connectivity rules enabled |
| Standard-cell row fill | PASS | Reachable `fill_1/2/4/8/16`, `filltie`, and `endcap` cells |
| Project dummy-purpose fill | PASS | No shapes on 34/4, 36/4, 42/4, 46/4, 81/4, or 53/4 |
| D04 VDD/VSS boundary connection | PASS | Explicit M2-M3-M4 routes and via stacks; all internal stripes connected |
| CTS and detailed routing | PASS | `reports/flow.complete`; `reports/route_drc.rpt` is empty |
| Post-route STA | PASS at ss/125°C/4.5 V | WNS/TNS 0.00; setup slack 74.67 ns; hold slack 1.49 ns |
| Max slew/capacitance/fanout | No reported violators | `reports/signoff/sta_ss_repair.rpt` |
| PDNSim | COMPLETED, diagnostic assumptions | Default block-level checkerboard VSRC model; package-aware analysis remains top-level work |
| Magic GDS extraction | PASS | Magic 8.3.465; `reports/lvs/extraction.complete` |
| Real transistor-level LVS | PASS | Unique match: 5,362 devices and 5,367 nets on each side |

## Integration-review repair

- The previous flow copied undersized signal-pin rectangles from the D04 reference after routing. It now retains OpenROAD's legal router-generated signal pins and copies only the disjoint D04 VDD/VSS geometry.
- KLayout-generated `VIA_*` helper cells now have independently legal landing metal. This removes the hierarchical M2/M3/M4 minimum-area dependency identified during chip-top integration.
- Signoff now runs the GF180 main deck twice—flat and deep—with FEOL, BEOL, and connectivity rules explicitly enabled, and fails closed on any result item.
- The canonical layout remains unfilled; density/antenna closure for the assembled chip remains the chip-top integration flow's responsibility.
- `uart_tx_IN` remains intentionally unused and is identically disconnected on both LVS sides.
