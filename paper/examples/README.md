# Chip Orchestra examples

This folder contains three examples. Everything is kept under the paper folder as requested.

| Folder | Contents | Evidence |
| --- | --- | --- |
| `fulladder` | One-bit full adder RTL, exhaustive testbench, mapped netlist, fresh OpenROAD implementation, binary GDS | All eight RTL and post-route gate-level cases pass |
| `cgra` | The optimized nine-PE NanoCGRA, 32-byte SRAM, UART interface, copied physical core and independent testbench | 192 arithmetic vectors and all 32 SRAM addresses pass at the default UART divisor 87 |
| `combined_padframe` | One GF180 padframe containing the full adder and NanoCGRA as separate physical core instances | Nine signal routes and four power routes are independently checked in the generated GDS |

## Open the result

The primary combined layout is `combined_padframe/padring/ChipOrchestraDualCore_chip.gds`. Open its `ChipOrchestraDualCore_chip` top in KLayout and show the full hierarchy. It has direct references to the original `RING_PAD`, `u_cgra__NanoCGRA_Lite`, and `u_fulladder__fulladder`. The full adder is the smaller block to the right of the CGRA.

`combined_padframe/padring/ChipOrchestraDualCore_chip_preview.png` is a native KLayout screenshot of that actual GDS. `two_core_detail.png` provides a closer view. The separate core screenshots are under each example's `gds` directory.

## Reproduce

Use Ubuntu WSL with the installed GF180MCU-D PDK and the existing Icarus, Yosys, OpenROAD, KLayout, and Python environments.

```bash
bash /mnt/d/LinkedinProjects/Chip-Orchestra/paper/examples/run.sh
```

The default command verifies both RTL designs, freshly builds the full adder, installs the existing NanoCGRA physical core with recorded provenance, generates the two-core padframe, checks the routed full adder, simulates both designs through the official GF180 IO models, and independently extracts top-level metal/via connectivity from the final GDS.

To regenerate the padframe from the supplied core inputs and rerun its checks, use `run.sh --assemble-only`. `--reharden-cgra` explicitly requests an additional fresh CGRA physical attempt. That optional hardening is separate from padframe generation and can take substantially longer. The attempted fresh run is preserved under `cgra/attempts/fresh_openroad`. It stopped during detailed routing and is not the source of the final core.

The provided shell script uses this computer's installed runtime paths. Another machine needs equivalent tools and a matching `PDK_ROOT`. Python dependencies for native assembly are declared in `eda-service/requirements.txt`.

## What was fixed

The legacy GF180 routing layer numbers were incorrect. The installed PDK maps Metal2 to stream layer 36, Metal3 to 42, Metal4 to 46, and Metal5 to 81. Explicit multi-core assembly now reads this mapping, actual DEF pin geometry, actual pad LEF pin geometry, pad-instance rotations, and the PDK's via rectangles. It routes around the two core footprints and checks same-layer intersections before writing GDS.

The compact full-adder macro uses Metal3 fanout to isolate its closely spaced pins from Metal4 power drops. The assembler ties 168 pad control pins, connects VDD and VSS to both cores, and chooses route widths at least as large as the PDK minimum. Native KLayout previews avoid the previous expensive flattening of the entire ring through Matplotlib.

The actual bundled ring contains 73 IO pads and four corners, along with fillers and break cells. Its census is read directly from GDS and recorded in `pin_assembly_report.json`. Nine pads are used for the two designs. The older deterministic supporting DEF, LEF, and generic ring netlist are schematic fallback views. They are not signoff views of this two-core chip. Use the binary GDS, assembly manifest, explicit RTL pad wrapper, and structured reports as the authoritative example artifacts.

## Validation and limits

Seven backend regression tests pass. The official GF180 IO-model simulation passes eight full-adder cases plus 224 CGRA checks. Independent readback checks nine separate signal connections, four supply connections, actual pad/core pin overlap, and all top-level via landings. Reports are retained in `combined_padframe/reports` and raw logs in `logs`.

NanoCGRA's physical GDS and DEF are retained existing artifacts. Its RTL is freshly checked. The full-adder physical implementation and combined padframe are newly generated. `cgra/reports/provenance.json` records the physical source and hash.

The connectivity check extracts the newly added top-level metal and via geometry. It is not full-chip device LVS, foundry DRC, antenna checking, or post-padframe timing signoff. No tapeout-ready or fabricated-chip claim is made. The pad models test functional IO behavior without extracted wire delays.
