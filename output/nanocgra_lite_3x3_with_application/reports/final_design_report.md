# Final Design Report — nano cgra 3x3 sobel accelerator v4

## Overview

- **Task ID:** `dbe7af46-366c-421b-8cf3-daafc5a7ae6a`
- **Top module:** `nano_cgra_3x3_sobel_accelerator_v4`
- **Signoff:** ✅ tapeout ready

## Design Brief

nano cgra 3x3 for sobel filter accelerator, i uploaded 2 images, 1 for you to understand the architecture of nano cgra what i want but for input output use UART, see it properly, and 1 for the reference image you build the sobel filter accelerator, uses 32x32 of that image, make sure the cropped image shows the road.

## Implementation Artifacts

### RTL sources
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

### Testbenches
- `tb/baud_gen_tb.v`
- `tb/cgra_3x3_tb.v`
- `tb/line_buffer_tb.v`
- `tb/mmio_bus_tb.v`
- `tb/nano_cgra_3x3_sobel_accelerator_v4_tb.v`
- `tb/nano_controller_tb.v`
- `tb/params_tb.v`
- `tb/pe_tb.v`
- `tb/reset_sync_tb.v`
- `tb/sobel_core_tb.v`
- `tb/sram_32b_tb.v`
- `tb/uart_rx_tb.v`
- `tb/uart_tx_tb.v`
- `tb/window_3x3_tb.v`

## Verification Evidence

- Compiled: `True`
- Waveform produced: `True`
- Waveforms: `waves/chip_input.png`, `waves/chip_output.mem`, `waves/chip_output.png`, `waves/design.vcd`, `waves/gl_nano_cgra_3x3_sobel_accelerator_v4`, `waves/gl_nano_cgra_3x3_sobel_accelerator_v4.vcd`, `waves/golden_output.mem`, `waves/golden_output.png`, `waves/waveform.json`, `waves/waveform.png`

## Hardware/Software Co-Verification

Simulation checks the RTL against the reference on the stimulus compiled into the
design. This stage checks the finished part the way software uses it: a host driver
encodes a user-supplied file into the chip's own wire format, an interface bench
replays it against the unmodified DUT, and the driver decodes the reply.

- **Interface:** Top module `nano_cgra_3x3_sobel_accelerator_v4` ports: input clk, input rst_async_n, input data_i, output data_o. Interface is BIT-SERIAL (UART-style): payload enters on `data_i` and leaves on `data_o`, one bit per baud period of 434 clock cycles, 8 data bits per frame, LSB first, with a low start bit and a high stop bit. Data geometry: input 32x32, output 30x30 bytes.
- **Host driver:** `sw/hwsw/host_driver.py`
- **Interface bench:** `tb/hwsw/nano_cgra_3x3_sobel_accelerator_v4_hwsw_tb.v` (existing)
- **Input:** `Screenshot_from_2026-08-01_05-48-03.png` (1024 bytes sent, 900 returned)
- **Reference entry point:** `golden/model/top.py::sobel_stream`
- **Verdict:** ✅ chip output matches the reference model

- Evidence: `hwsw/input_preview.png`, `hwsw/expected_output.png`, `hwsw/chip_output.png`, `hwsw/waveform.png`

## Physical Results

| Metric | Value |
| --- | --- |
| compiled | True |
| waveform | True |
| passed | True |
| golden_match | True |
| signal_count | 32 |
| checked_files | 14 |
| clean | True |
| warning_count | 0 |
| die_area_um2 | 246939 |
| die_bbox_um | 0.0 0.0 488.05 505.97 |
| core_area_um2 | 224979 |
| cell_count | 10553 |
| util_pct | 0.424181 |
| io_pins | 6 |
| wns_ns | 0.4801830180503395 |
| tns_ns | 0 |
| hold_wns_ns | 0.22471247720850843 |
| power_mw | 0.025658758357167244 |
| antenna_violations | 0 |
| drc_errors | 0 |
| max_slew_violations | 0 |
| max_cap_violations | 0 |
| max_fanout_violations | 0 |
| setup_ws_tt_ns | 13.361870210705904 |
| setup_ws_ss_ns | 0.4801830180503395 |
| setup_ws_ff_ns | 18.999234723247483 |
| clock_period_ns | 28.33 |
| clock_target_mhz | 35.3 |
| fmax_mhz | 35.9 |
| voltage | 5.0V |
| timing_met | True |
| engine | opensta |
| rendered | 4 |
| images | ['reports/schematic.png', 'reports/waveform.png', 'reports/gds.png', 'reports/metrics.png'] |
| skipped | True |
| config | none |

- GDS artifacts: `gds/nano_cgra_3x3_sobel_accelerator_v4.gds`, `gds/nano_cgra_3x3_sobel_accelerator_v4.png`

## Stage Reports

- `DRC_LVS`
- `GL_SIM`
- `HW_SW_VERIFY`
- `LINT`
- `PADRING`
- `PNR`
- `RENDER`
- `SIM`
- `STA`
- `SYNTH`

