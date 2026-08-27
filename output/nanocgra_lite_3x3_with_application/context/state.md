# context/state.md — Run journal

Every stage appends here; deep agents read this FIRST.

- **2026-08-15 03:11 · spec_ingest:done** — brief captured; attachments=['Screenshot_from_2026-07-14_16-24-31.png', 'Screenshot_from_2026-08-01_19-42-51.png']; vision digest at context/uploads_digest.md
- **2026-08-15 03:25 · planning:done** — Grand plan written. Architecture: 3×3 CGRA (9 PEs) + NanoController FSM + MMIO bus + 32B SRAM + UART I/O, streaming Sobel on 32×32 image. Top module: nano_cgra_3x3_sobel_accelerator_v4. 14 RTL files planned. Input crop: (20,340) 32×32 from highway image showing road. References studied: stffrdhrn/uart, 123-code/cnn_chip, pnnl/OpenCGRA. Plan at plans/execution_plan.md, contract at context/design_notes.md. Area budget ~997 FFs, well under 2000 limit.- **2026-08-15 03:14 · plan:done** — mode=deep agent + web research; planned rtl files=['reset_sync.v', 'uart_rx.v', 'uart_tx.v', 'baud_gen.v', 'line_buffer.v', 'window_3x3.v', 'pe.v', 'cgra_3x3.v', 'sobel_core.v', 'sram_32b.v', 'mmio_bus.v', 'nano_controller.v', 'nano_cgra_3x3_sobel_accelerator_v4.v', 'params.vh', 'sobel_input.mem', 'sobel_golden.mem']
- **2026-08-15 03:45 · golden:done** — ips=['baud_gen', 'cgra_3x3', 'line_buffer', 'mmio_bus', 'nano_controller', 'params', 'pe', 'reset_sync', 'sobel_core', 'sram_32b', 'uart_rx', 'uart_tx', 'window_3x3']; tests=52 passed/0 failed; previews=['waves/chip_input.png', 'waves/golden_output.png']; gaps=['context/golden_contract.md — the BUILD CONTRACT for RTL_GEN/TB_GEN: a table of | module | rtl/<file>.v | tier (ip/subtop/top) | role | ports (name, dir, width) | and the fixed-point format of every datapath signal.', 'golden/golden_summary.json — the manifest the review popup renders: {"top":..., "ips":[{"name","file","tier","role","ports"}], "notes":...}', 'golden/module_math.json — the per-module explanation + governing equations the IEEE report renders: {"algorithm":{"summary","equations":[latex]}, "modules":[{"name","purpose","io","equations":[latex]}]}, covering every module in the build contract.']
- **2026-08-15 09:59 · generate:done** — files=['baud_gen.v', 'cgra_3x3.v', 'line_buffer.v', 'mmio_bus.v', 'nano_controller.v', 'pe.v', 'reset_sync.v', 'sobel_core.v', 'sram_32b.v', 'uart_rx.v', 'uart_tx.v', 'window_3x3.v'], broken=none, planned-missing=['nano_cgra_3x3_sobel_accelerator_v4.v'], ips=['baud_gen', 'line_buffer', 'mmio_bus', 'nano_controller', 'pe', 'reset_sync', 'sobel_core', 'sram_32b', 'window_3x3'], subtops=['uart_rx', 'uart_tx'], top=cgra_3x3, structure-gaps=['the golden contract defines these IP blocks but no RTL module implements them — write rtl/<name>.v for each: params']
- **2026-08-15 10:00 · generate:per-module** — sweep 1 (limit 50) wrote=['baud_gen.v', 'cgra_3x3.v', 'line_buffer.v', 'mmio_bus.v', 'nano_controller.v', 'pe.v', 'reset_sync.v', 'sobel_core.v', 'sram_32b.v', 'uart_rx.v', 'uart_tx.v', 'window_3x3.v']; still-missing=['params']
- **2026-08-15 10:00 · generate:per-module** — sweep 2 (limit 80) wrote=['baud_gen.v', 'cgra_3x3.v', 'line_buffer.v', 'mmio_bus.v', 'nano_controller.v', 'params.v', 'pe.v', 'reset_sync.v', 'sobel_core.v', 'sram_32b.v', 'uart_rx.v', 'uart_tx.v', 'window_3x3.v']; still-missing=none
- **2026-08-15 10:22 · generate:done** — files=['baud_gen.v', 'cgra_3x3.v', 'line_buffer.v', 'mmio_bus.v', 'nano_cgra_3x3_sobel_accelerator_v4.v', 'nano_controller.v', 'params.v', 'pe.v', 'reset_sync.v', 'sobel_core.v', 'sram_32b.v', 'uart_rx.v', 'uart_tx.v', 'window_3x3.v'], broken=none, planned-missing=none, ips=['baud_gen', 'line_buffer', 'mmio_bus', 'nano_controller', 'params', 'pe', 'reset_sync', 'sobel_core', 'sram_32b', 'window_3x3'], subtops=['cgra_3x3', 'uart_rx', 'uart_tx'], top=nano_cgra_3x3_sobel_accelerator_v4, structure-gaps=none
- **2026-08-15 10:36 · testbench:done** — testbenches=['baud_gen_tb.v', 'cgra_3x3_tb.v', 'line_buffer_tb.v', 'mmio_bus_tb.v', 'nano_cgra_3x3_sobel_accelerator_v4_tb.v', 'nano_controller_tb.v', 'params_tb.v', 'pe_tb.v', 'reset_sync_tb.v', 'sobel_core_tb.v', 'sram_32b_tb.v', 'uart_rx_tb.v', 'uart_tx_tb.v', 'window_3x3_tb.v']; unit coverage=13/13; uncovered=none; top tb clean=True
- **2026-08-15 10:41 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 10:46 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 10:56 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 11:01 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 11:10 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 11:34 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 17:40 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 17:47 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 17:54 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 18:02 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 18:09 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 18:16 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 18:23 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 18:30 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 18:37 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-15 19:20 · repair:sim-failure** — debugged failing simulation; broken=none
- **2026-08-16 00:47 · repair:hardening** — targeted repair applied; broken=none
- **2026-08-16 00:52 · repair:hardening** — targeted repair applied; broken=none
- **2026-08-16 00:55 · repair:hardening** — targeted repair applied; broken=none
- **2026-08-16 02:00 · repair:regression** — 1 architecture violation(s) reintroduced
- **2026-08-16 02:02 · repair:regression** — 1 architecture violation(s) reintroduced
- **2026-08-16 02:03 · repair:hardening** — targeted repair applied; broken=none
- **2026-08-16 06:12 · repair:hardening** — targeted repair applied; broken=none
- **2026-08-16 06:21 · repair:hardening** — targeted repair applied; broken=none
- **2026-08-16 09:00 · repair:hardening** — targeted repair applied; broken=none
