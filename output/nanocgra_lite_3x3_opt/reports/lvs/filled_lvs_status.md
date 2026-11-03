# Historical filled-layout LVS status (withdrawn)

Project-generated dummy fill and the legacy `_filled.gds` are not part of the
canonical integration flow. The former filled-layout/empty-stub LVS claim is
withdrawn and must not be used as signoff evidence.

Current authoritative LVS evidence is:

- `reports/lvs/netgen_final.log`
- `reports/lvs/comp_final.out`
- `reports/lvs/netgen.complete`
- `reports/lvs/d04_lvs_status.md`

The current comparison uses real Magic extraction of the canonical unfilled GDS
against source SPICE generated independently from powered post-route Verilog and
official GF180 PDK CDL pin order.
