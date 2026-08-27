# Golden Model Report — nano_cgra_3x3_sobel_accelerator_v4

## 1. Architecture Overview

A streaming Sobel edge-detection accelerator built around a 3×3 CGRA
(9 Processing Elements), controlled by a microcoded NanoController FSM
sequencer, with UART serial I/O and a lightweight 8-bit MMIO
interconnect. The chip receives a 32×32 grayscale image one byte at a
time over UART, processes it through the 3×3 CGRA Sobel engine, and
streams the 30×30 edge-map result back out over UART.

On-chip storage is limited to the operator working set — two 32-byte
line buffers (rows N-2 and N-1) plus a 3×3 window register file and a
32-byte SRAM scratch — **not** a full frame buffer. Each Sobel result
is emitted on UART TX as soon as it is computed, so input reception
and output transmission overlap.

### Block diagram (data flow)

```
Host PC ──UART TX (data_i)──► uart_rx ──rx_byte,rx_valid──► nano_controller
                                                              │ pixel_in, pixel_shift
                                                              ▼
                                              line_buffer[0] (row N-2)
                                              line_buffer[1] (row N-1)
                                                              │ lb0,lb1,cur
                                                              ▼
                                                        window_3x3 ──win[0:8]──► cgra_3x3
                                                                                      │ sobel_out, done
                                                                                      ▼
                                              nano_controller ◄── sobel_out ──────────────
                                                      │ tx_data, tx_start
                                                      ▼
                                                   uart_tx ──data_o──► Host PC

nano_controller ──bus_addr/bus_wr/bus_wdata──► mmio_bus ──► sram_32b (scratch)
                                                          ──► cgra_3x3 (config/status)
                                                          ──► uart_tx  (TXDATA reg)
reset_sync ──rst_n──► all blocks
baud_gen  ──baud_tick──► uart_rx, uart_tx
```

## 2. IP / Module Table

| # | Module | File | Tier | Role |
|---|--------|------|------|------|
| 1 | reset_sync | rtl/reset_sync.v | ip | Power-on + 2-flop synchronous reset generator |
| 2 | baud_gen | rtl/baud_gen.v | ip | Baud-rate tick generator (1 pulse per bit period) |
| 3 | uart_rx | rtl/uart_rx.v | ip | UART receiver: serial→byte, start/data/stop FSM |
| 4 | uart_tx | rtl/uart_tx.v | ip | UART transmitter: byte→serial, latched start req |
| 5 | line_buffer | rtl/line_buffer.v | ip | 32-byte shift register storing one image row |
| 6 | window_3x3 | rtl/window_3x3.v | ip | 3×3 window assembler from 2 line buffers + cur pixel |
| 7 | pe | rtl/pe.v | ip | Single Processing Element (8-bit ALU, shift-add weights) |
| 8 | cgra_3x3 | rtl/cgra_3x3.v | subtop | 3×3 PE mesh array, Sobel Gx/Gy compute + magnitude |
| 9 | sobel_core | rtl/sobel_core.v | ip | Pure combinational Sobel Gx/Gy + saturate (reference datapath) |
| 10 | sram_32b | rtl/sram_32b.v | ip | 32-byte single-port SRAM scratch |
| 11 | mmio_bus | rtl/mmio_bus.v | ip | 8-bit MMIO interconnect / address decoder |
| 12 | nano_controller | rtl/nano_controller.v | subtop | Microcoded FSM sequencer (cmd decode, addr gen, loop, status) |
| 13 | nano_cgra_3x3_sobel_accelerator_v4 | rtl/nano_cgra_3x3_sobel_accelerator_v4.v | top | TOP module integrating all blocks |

Shared macros live in `rtl/params.vh`.

## 3. Fixed-Point / Data Formats

| Signal class | Format | Range | Notes |
|--------------|--------|-------|-------|
| Pixel / data byte | unsigned 8-bit | 0..255 | grayscale, UART payload |
| Sobel kernel weight | signed small int | {-2,-1,0,+1,+2} | implemented as shifts+adds, no multiplier |
| Gx, Gy partial sums | signed 9-bit | -510..+510 | sum of up to 6 weighted 8-bit pixels |
| \|Gx\|+\|Gy\| magnitude | unsigned 10-bit | 0..1020 | before saturation |
| sobel_out | unsigned 8-bit | 0..255 | min(magnitude,255) |
| MMIO address | unsigned 8-bit | 0x00..0xFF | 256-location address space |
| SRAM address | unsigned 5-bit | 0..31 | 32-byte scratch |
| col_cnt / row_cnt | unsigned 6-bit | 0..31 | image geometry counters |
| status | 8-bit | {6'b0, done, busy} | bit0=busy, bit1=done |

No fractional fixed-point is used: all datapath arithmetic is integer.
The only "quantization" is the final saturation `min(|Gx|+|Gy|, 255)`.

## 4. Sobel Algorithm

For each valid 3×3 window `w[0..8]` (row-major, 0=top-left … 8=bot-right):

```
Gx = -w0 + w2 - 2*w3 + 2*w5 - w6 + w8
Gy = -w0 - 2*w1 - w2 + w6 + 2*w7 + w8
out = min( |Gx| + |Gy| , 255 )
```

Kernels:
```
Gx = [-1  0 +1]      Gy = [-1 -2 -1]
     [-2  0 +2]           [ 0  0  0]
     [-1  0 +1]           [+1 +2 +1]
```

Coefficients are 0, ±1, ±2 → implemented with shifts and adds only
(PE cfg: PASS=+1, NEG=-1, SHL1=+2, NEG_SHL1=-2, ZERO=0). No general
multiplier is needed for the Sobel weights.

## 5. Input Data

- Source image: `context/uploads/Screenshot_from_2026-07-14_16-24-31.png`
  (highway scene with road surface, vehicles, lane markings).
- A 32×32 region showing the road is extracted and converted to
  grayscale `Y = 0.299R + 0.587G + 0.114B`, rounded to 8-bit.
- The 1024-byte flat pixel array is stored in
  `context/chip_input_grid.json` and `rtl/sobel_input.mem` (hex, one
  byte per line, `$readmemh`).
- The golden Sobel output (900 bytes) is in
  `waves/golden_output.mem` and `golden/outputs/sobel_result.json`.

## 6. What Each Test Proves

| Test file | Module exercised | What it proves |
|-----------|------------------|----------------|
| test_reset_sync.py | reset_sync | rst_n asserted on power-on, held while async low, deasserts synchronously after 2 clocks |
| test_baud_gen.py | baud_gen | exactly 1 tick per DIV=CLK_FREQ/BAUD_RATE clocks; no ticks in reset |
| test_uart_rx.py | uart_rx | receives 0xA5/0x00/0xFF correctly; exactly one rx_valid pulse per frame |
| test_uart_tx.py | uart_tx | transmits 0x3C/0xFF correctly; start/data/stop frame sampled at bit midpoints; tx_start latched so 1-cycle pulse is never dropped |
| test_line_buffer.py | line_buffer | shift-in, overflow, no-shift-when-disabled, reset clears |
| test_window_3x3.py | window_3x3 | 3×3 window forms after 3 rows×3 cols; not valid before; correct row-major contents |
| test_pe.py | pe | all cfg ops (pass/zero/shl1/neg/neg_shl1/abs/mul/add) and reset |
| test_cgra_3x3.py | cgra_3x3 | flat→0, vertical edge→255, matches sobel_core on 20 random windows |
| test_sobel_core.py | sobel_core | flat=0, vertical/horizontal edges, hand-computed values, no-saturation case |
| test_sram_32b.py | sram_32b | write/read all addresses, reset clears |
| test_mmio_bus.py | mmio_bus | SRAM/UART/CGRA/START selects, SRAM write strobe, reset |
| test_nano_controller.py | nano_controller | IDLE→RECV on first rx_valid, pixel counting, row advance |
| test_top.py | top (functional) | output size 30×30, streaming model matches direct 2D Sobel reference, known-value spot check, all bytes 0..255 |

## 7. What the Output Means

The 30×30 `sobel_out` array is an edge magnitude map: each pixel is
`min(|Gx|+|Gy|,255)` for the corresponding 3×3 neighborhood of the
input. Bright pixels (→255) mark strong edges (lane markings, vehicle
boundaries, road/sky transitions); dark pixels (→0) mark flat regions.
The streaming model emits these in row-major order, one byte per UART
frame, as soon as each window becomes valid.

## 8. Test-Vector Export

`golden/vectors/<module>.json` contains per-module test vectors with
INTEGER (already-quantized) input/expected values that TB_GEN turns
into Verilog testbenches. Each file has the schema:
```json
{"module": "...",
 "ports": {"inputs": [[name,width]...], "outputs": [[name,width]...]},
 "vectors": [{"inputs": {...}, "expected": {...}}, ...]}
```
13 vector files are exported, one per module in the build contract.

## 9. Verification Status

`python -m pytest golden/tests -q` → **52 passed, 0 failed**.
All golden-model assertions hold; no test was weakened, skipped, or
deleted.