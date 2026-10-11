# NanoCGRA run and padframe evidence

Run date: October 11, 2026, Asia/Jakarta.

## Outcome

A fresh RTL-to-physical flow was attempted using the existing UART-only NanoCGRA RTL and the repository EDA runners. Fresh top-level simulation and syntax checking passed. Synthesis completed. Physical implementation stopped before placement at an OpenSTA and LibreLane compatibility failure. Separately, a new padframe assembly successfully reused the retained NanoCGRA physical core. KLayout read the generated binary GDSII and captured the screenshot included as Fig. 3 in the revised four-page paper.

This is not a completed fresh end-to-end signoff flow. The generated pad-to-core routes are explicitly best-effort geometric routes. Full-chip electrical connectivity, DRC, and LVS remain unverified.

## Fresh run

Workspace: `nanocgra_e2e_20261011`.

Inputs: copied RTL and testbenches from `output/nanocgra_lite_3x3_opt`. Existing outputs were not modified. No LLM generation, task submission, golden-model approval, or browser orchestration was performed. The EDA runner functions were invoked directly.

- SRAM UART readback passes with expected and actual value 123.
- CGRA addition passes with expected and actual value 8.
- CGRA multiplication passes with expected and actual value 144.
- CGRA exclusive-or passes with expected and actual value 85.
- Icarus syntax and elaboration checks pass.
- Verilator in the hardening flow reports 298 warnings, so the result is not described as warning-free lint.
- Synthesis finishes with mapped gate area 129,736.32 square micrometers. This is a fresh synthesis metric, distinct from retained implementation metrics in the paper.
- Fresh place and route did not start. No fresh core GDSII was produced.

The copied top-level testbench originally prints `Result: PASSED`. The repository runner requires `TEST PASSED`, so verdict strings were adapted in the copy. A top-level waveform dump was added. The assertions and RTL were unchanged.

## Tool compatibility attempts

1. The installed Yosys 0.38 binary does not support `yosys -y`, required by LibreLane 3.x Python steps.
2. An isolated Python synthesis shim and the Dockerfile-pinned LibreLane 3.0.7 and pyosys 0.66 dependencies were used. This allowed synthesis to complete.
3. OpenSTA 2.5.0 rejected `report_checks -group_path_count`. In the isolated runtime only, that reporting flag was adapted to the older `-group_count` name. Constraints were unchanged.
4. Pre-placement STA then failed because this OpenSTA version lacks the clock `is_propagated` property expected by the reporting script. The flow was not bypassed or marked successful.

The installed GF180MCU PDK is revision `bdc9412b3e468c102d01b7cf6337be06ec6e9c9a`. The fresh hardening configuration selects 5 V libraries and a 100 ns clock. Python dependencies are in `paper/eda_runtime`. Run inputs, reports, and tool logs are retained.

## Successful assembly

Workspace: `nanocgra_padframe_20261011`.

The core GDSII and DEF were copied from the existing optimized NanoCGRA output. The source core is `output/nanocgra_lite_3x3_opt/gds/nanocgra_lite_3x3_opt.gds`. The ring is the repository's `eda-service/toolchain/gf180/RING_PAD.gds`. The existing `run_padring` function was executed with `gf180-v1`.

| Result | Recorded value |
|---|---|
| Core bounding box | 466.555 × 466.555 micrometers |
| Ring and chip extents | 2935 × 2935 micrometers |
| Configured chip area | 8.614225 square millimeters |
| Translation | 1254.523 micrometers in x and y |
| Merged GDS cells | 993 |
| Configured I/O resources | 69 pads plus four corners |
| Signal route polygons | Four on Metal2 |
| Supply route polygons | Seven on Metal3 |
| Matched signal names | clk, rst_n, uart_rx, uart_tx |
| Chip top | NanoCGRA_Lite_chip |
| Direct child instances | RING_PAD and NanoCGRA_Lite |

The assembled GDSII is `nanocgra_padframe_20261011/padring/NanoCGRA_Lite_chip.gds`. Supporting configuration, DEF, LEF, Verilog, report JSON, and logs are in that workspace.

The repository Matplotlib renderer flattened a large hierarchy and consumed substantial memory. It was stopped and disabled in the task-local wrapper. Assembly itself was unchanged. The screenshot was instead captured directly by KLayout from the generated GDSII with the full hierarchy visible. The display grid and shape labels were hidden for publication readability. The 2200 × 2200 PNG is included at 3.3 inches in the revised paper, approximately 667 dpi. It is not a schematic or AI-generated image.

## Reproduce

In the same WSL environment, run `bash paper/run_nanocgra_e2e.sh` for the fresh EDA attempt. This retains the known OpenSTA compatibility limitation.

Run `paper/assemble_retained_nanocgra.py` with the isolated Python runtime on `PYTHONPATH` for the successful retained-core assembly. Use `paper/klayout_padframe_screenshot.py` with the `CHIP_GDS` and `CHIP_IMAGE` environment variables to capture the generated layout in KLayout.

The revised paper preserves all author emails and their shared ITB affiliation. It distinguishes newly executed simulation and assembly results from retained physical implementation results.
