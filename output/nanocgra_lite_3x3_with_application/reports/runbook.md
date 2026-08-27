# Runbook — nano cgra 3x3 sobel accelerator v4

## Reproduce the flow

```bash
# 1. Simulation (RTL + testbench)
iverilog -g2012 -o exports/sim.vvp -I rtl rtl/*.v tb/*.v
vvp exports/sim.vvp   # writes waves/design.vcd

# 2. Hardening (RTL -> GDSII)
librelane --manual-pdk --pdk-root $PDK_ROOT exports/harden/chip/config.json
```

## Key artifacts

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
- `waves/chip_input.png`
- `waves/chip_output.mem`
- `waves/chip_output.png`
- `waves/design.vcd`
- `waves/gl_nano_cgra_3x3_sobel_accelerator_v4`
- `waves/gl_nano_cgra_3x3_sobel_accelerator_v4.vcd`
- `waves/golden_output.mem`
- `waves/golden_output.png`
- `waves/waveform.json`
- `waves/waveform.png`
- `gds/nano_cgra_3x3_sobel_accelerator_v4.gds`
- `gds/nano_cgra_3x3_sobel_accelerator_v4.png`

## Debug tips

- If no `waves/design.vcd`, add `$dumpfile("design.vcd"); $dumpvars(0, nano_cgra_3x3_sobel_accelerator_v4_tb);` to the testbench.
- If synthesis fails with a combinational-network error, check the detected `CLOCK_PORT`.
- Review `logs/sim.log` and `logs/librelane.log` for the raw tool output.

