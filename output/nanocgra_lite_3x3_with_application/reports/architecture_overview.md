# Architecture Overview — nano cgra 3x3 sobel accelerator v4

- **Top module:** `nano_cgra_3x3_sobel_accelerator_v4`

## Module Inventory

- `rtl/baud_gen.v`
- `rtl/cgra_3x3.v`
- `rtl/line_buffer.v`
- `rtl/mmio_bus.v`
- `rtl/nano_cgra_3x3_sobel_accelerator_v4.v`
- `rtl/nano_controller.v`
- `rtl/params.v`
- `rtl/params.vh`
- `rtl/pe.v`
- `rtl/reset_sync.v`
- `rtl/sobel_core.v`
- `rtl/sobel_golden.mem`
- `rtl/sobel_input.mem`
- `rtl/sram_32b.v`
- `rtl/uart_rx.v`
- `rtl/uart_tx.v`
- `rtl/window_3x3.v`

## Design Notes

# RTL Architecture — nano_cgra_3x3_sobel_accelerator_v4

Generated for task nano cgra 3x3 sobel accelerator v4 by the RLM deep agent, implementing the Python golden model in `golden/`.

- **Top module:** `nano_cgra_3x3_sobel_accelerator_v4`
- **Sub-toplevel(s):** `cgra_3x3`, `uart_rx`, `uart_tx`
- **Leaf IPs:** `baud_gen`, `line_buffer`, `mmio_bus`, `nano_controller`, `params`, `pe`, `reset_sync`, `sobel_core`, `sram_32b`, `window_3x3`
- **Files:** `rtl/baud_gen.v`, `rtl/cgra_3x3.v`, `rtl/line_buffer.v`, `rtl/mmio_bus.v`, `rtl/nano_cgra_3x3_sobel_accelerator_v4.v`, `rtl/nano_controller.v`, `rtl/params.v`, `rtl/pe.v`, `rtl/reset_sync.v`, `rtl/sobel_core.v`, `rtl/sram_32b.v`, `rtl/uart_rx.v`, `rtl/uart_tx.v`, `rtl/window_3x3.v`
- **Compile check:** all clean ✓
- **Structure:** multi-file Verilog-2001, one module per file ✓


## Data Flow

1. Spec is ingested and decomposed into interfaces and constraints.
2. RTL is generated for the top module and its submodules.
3. A self-checking testbench drives functional verification (SIM).
4. LINT / SYNTH / PNR / DRC_LVS harden the design to GDSII.
5. SIGNOFF and EXPORT assemble the evidence-backed reports.

