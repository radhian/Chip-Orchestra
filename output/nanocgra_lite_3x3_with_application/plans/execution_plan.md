# Execution Plan — nano_cgra_3x3_sobel_accelerator_v4

## Overview
A streaming Sobel edge-detection accelerator built around a 3×3 CGRA (9 PEs),
controlled by a microcoded NanoController FSM sequencer, with UART serial I/O.
The chip receives a 32×32 grayscale image one byte at a time over UART,
processes it through the 3×3 CGRA Sobel engine, and streams the 30×30 result
back out over UART. On-chip storage is limited to the operator working set
(2 line buffers + 3×3 window registers), NOT a full frame buffer.

## Architecture (from uploaded diagram)
The architecture image shows:
- **Host (PC/MCU)** ↔ UART (2-wire RX/TX)
- **NanoController (FSM Sequencer)**: UART command decoder, config registers,
  address generator, loop counter, sequencer FSM, status logic, MMIO master
- **3×3 CGRA Accelerator**: 9 PEs (PE0–PE8), each 8-bit MAC/ALU, mesh
  interconnect with N/W/E/S interfaces
- **Lightweight MMIO Interconnect (8-bit)**: simple address decoder connecting
  SRAM, UART regs, CGRA config/status
- **SRAM (Macro)**: 32 B (256-bit), single port
- **UART (Memory Mapped)**: TX, RX, STATUS/CTRL, BAUD GEN
- **RESET LOGIC**: power-on reset, sync reset gen

### Memory Map (8-bit address space, 256 locations)
| Address Range | Region                  | Size | Access |
|---------------|-------------------------|------|--------|
| 0x00–0x1F     | SRAM data               | 32 B | R/W    |
| 0x80–0x83     | UART regs (TX/RX/STAT/CTRL) | 4 B | R/W    |
| 0x90–0x98     | CGRA config (cfg0..cfg8) | 9 B | R/W    |
| 0x99–0x9B     | CGRA operands (opa/opb/res) | 3 B | R/W    |
| 0xA0          | START (kick CGRA run)   | 1 B  | W      |
| 0xA1          | STATUS {6'b0,done,busy} | 1 B  | R      |

## Research / References Used
1. **stffrdhrn/uart** (`context/refs/https___github_com_stffrdhrn_uart.v`) —
   UART RX/TX FSM patterns: 4x-oversample RX, bit-count TX, start/data/stop
   states. Adapted to parameterized CLK_FREQ/BAUD_RATE tick-counter style.
2. **123-code/cnn_chip** (`context/refs/https___github_com_123_code_cnn_chip.v`) —
   UART RX/TX with tick-counter, control_unit FSM (IDLE→LOAD→COMPUTE→TX_RESULT),
   image RAM write-on-rx-valid pattern. Key lesson: their design buffered the
   full 784-byte frame in flip-flop RAM — we AVOID this by streaming through
   line buffers instead.
3. **pnnl/OpenCGRA** (`context/refs/https___deepwiki_com_pnnl_OpenCGRA.md`) —
   CGRA tile structure: FlexibleFu (configurable ALU), Crossbar routing,
   CtrlMem for config, ConstQueue for constants. Adapted to a fixed 3×3 mesh
   with neighbor-pass routing for Sobel stencil.
4. **Sobel VLSI paper** (ijraset.com) — Sobel operator math: Gx and Gy 3×3
   kernels with coefficients {±1,±2,±1,0}, magnitude = |Gx|+|Gy| (approx) or
   sqrt(Gx²+Gy²). We use |Gx|+|Gy| with saturation to 8-bit.

## Sobel Algorithm
- Input: 32×32 grayscale (8-bit/pixel), streamed row-by-row over UART
- 3×3 Sobel kernels:
  - Gx = [-1 0 +1; -2 0 +2; -1 0 +1] · window
  - Gy = [-1 -2 -1; 0 0 0; +1 +2 +1] · window
- Output: |Gx| + |Gy|, saturated to 255, for each valid 3×3 window position
- Result: 30×30 edge map (border pixels excluded), streamed out over UART
- Coefficients are 0, ±1, ±2 → shifts and adds only, NO multipliers

## Streaming Architecture (Area Budget Compliance)
- **2 line buffers** of 32 bytes each (2 × 32 × 8 = 512 bits) — store rows
  N-2 and N-1 while row N arrives
- **3×3 window registers** (9 × 8 = 72 bits) — formed from line buffers + 
  incoming pixel via shift logic
- **No frame buffer** — each Sobel result is emitted on UART TX as soon as
  computed
- Total storage: ~512 + 72 + control regs ≈ 700 bits ≈ ~45 FFs for storage
  + ~200 FFs for control/UART = well under 2000 FF budget

## Module Map (every rtl/<file>.v)

| # | File | Module | Role | Key Ports/Widths |
|---|------|--------|------|------------------|
| 1 | `rtl/params.vh` | (macros) | Shared parameters: CLK_FREQ, BAUD_RATE, IMG_W, IMG_H, DATA_W, addr map | `define CLK_FREQ 50000000, BAUD_RATE 115200, IMG_W 32, IMG_H 32, DATA_W 8 |
| 2 | `rtl/reset_sync.v` | reset_sync | Power-on + synchronous reset generator | clk, rst_async_n → rst_n (synced) |
| 3 | `rtl/uart_rx.v` | uart_rx | UART receiver: serial→byte, tick-counter based | clk, rst_n, rx_in → rx_byte[7:0], rx_valid |
| 4 | `rtl/uart_tx.v` | uart_tx | UART transmitter: byte→serial, tick-counter based | clk, rst_n, tx_start, data_in[7:0] → tx_out, tx_done |
| 5 | `rtl/baud_gen.v` | baud_gen | Baud rate divider (optional, can fold into UART) | clk → baud_tick (1 pulse per bit period) |
| 6 | `rtl/line_buffer.v` | line_buffer | 32-byte shift register storing one image row | clk, rst_n, shift_en, pixel_in[7:0] → row_out[31:0][7:0] (or tap output) |
| 7 | `rtl/window_3x3.v` | window_3x3 | Assembles 3×3 window from 2 line buffers + incoming pixel | clk, rst_n, pixel_in[7:0], shift_en → w[0:8] (9×8-bit window) |
| 8 | `rtl/pe.v` | pe | Single Processing Element: 8-bit ALU/MAC with config | clk, rst_n, cfg[2:0], opa[7:0], opb[7:0], result[7:0], neighbor_in/out |
| 9 | `rtl/cgra_3x3.v` | cgra_3x3 | 3×3 CGRA array: 9 PEs in mesh, N/W/E/S interfaces, Sobel compute | clk, rst_n, window[0:8], cfg[8:0], start → gx[7:0], gy[7:0], done |
| 10 | `rtl/sobel_core.v` | sobel_core | Sobel Gx/Gy computation using shifts+adds, magnitude saturate | gx_win[0:8], gy_win[0:8] → sobel_out[7:0] |
| 11 | `rtl/sram_32b.v` | sram_32b | 32-byte single-port SRAM macro model | clk, addr[4:0], wr_en, data_in[7:0] → data_out[7:0] |
| 12 | `rtl/mmio_bus.v` | mmio_bus | 8-bit MMIO interconnect / address decoder | clk, rst_n, bus_addr[7:0], bus_wr, bus_rd, bus_wdata[7:0] → bus_rdata[7:0], slave selects |
| 13 | `rtl/nano_controller.v` | nano_controller | Microcoded FSM sequencer: command decode, address gen, loop counter, status | clk, rst_n, rx_byte[7:0], rx_valid, tx_done, cgra_done → bus_addr, bus_wr, bus_wdata, start_cgra, state_out |
| 14 | `rtl/nano_cgra_3x3_sobel_accelerator_v4.v` | nano_cgra_3x3_sobel_accelerator_v4 | TOP: integrates UART, NanoController, MMIO bus, CGRA, SRAM, line buffers, window, Sobel core | clk, rst_n, data_i (UART RX), data_o (UART TX) |

## Data Flow (Streaming)
```
Host PC
  │ UART TX (data_i pin)
  ▼
uart_rx ──rx_byte[7:0], rx_valid──► nano_controller
                                        │ MMIO bus (addr[7:0], wdata[7:0])
                                        ▼
                              mmio_bus ──► sram_32b (32 B scratch)
                                        ──► cgra_3x3 (config/operands)
                                        ──► uart_tx (TXDATA reg)
                                        
nano_controller FSM:
  IDLE → RECV_PIXELS (stream 32×32 bytes in, feed to line_buffer chain)
       → COMPUTE (for each valid window: assemble 3×3, run CGRA Sobel)
       → TX_RESULT (stream 30×30 result bytes out via uart_tx)
       → IDLE

Line buffer chain:
  pixel_in → line_buffer[0] (row N-2) → line_buffer[1] (row N-1) → current pixel (row N)
  window_3x3 taps 3 pixels from each of 3 rows → 3×3 window
  cgra_3x3 computes Gx, Gy via 9 PEs (each PE does one kernel multiply-accumulate)
  sobel_core combines: |Gx| + |Gy|, saturate to 8-bit
  Result → uart_tx → data_o pin → Host PC
```

## Testbench Plan
- `tb/nano_cgra_3x3_sobel_accelerator_v4_tb.v` — top-level testbench
  - Generates 50 MHz clock, applies reset
  - Pre-processes the highway image: crop 32×32 road region (x=20, y=340),
    convert to grayscale, save as `rtl/sobel_input.mem` ($readmemh format)
  - Drives UART RX pin with 32×32 = 1024 input bytes at 115200 baud
  - Captures UART TX output (30×30 = 900 result bytes)
  - Compares against Python golden model (Sobel on same 32×32 crop)
  - Visualizes input and output to `waves/chip_input.png` and `waves/chip_output.png`
- `tb/uart_rx_tb.v` — unit test for UART receiver
- `tb/uart_tx_tb.v` — unit test for UART transmitter (loopback)
- `tb/cgra_3x3_tb.v` — unit test for CGRA Sobel computation
- `tb/window_3x3_tb.v` — unit test for 3×3 window assembly from line buffers

## Simulation Steps
1. Unit-test each module: uart_rx, uart_tx, line_buffer, window_3x3, pe, cgra_3x3, sobel_core
2. Integration test: nano_controller + mmio_bus + sram + cgra
3. Full system test: top module with UART I/O, 32×32 image input, 30×30 output
4. Golden model comparison: Python Sobel on same crop, compare byte-by-byte

## Lint Steps
- Check all modules for Verilog-2001 compliance (no logic/always_ff/sv)
- Verify one driver per signal, no multi-driven regs
- Check reset of unpacked arrays via for-loop (not mem<=0)
- Verify replication uses double braces {{N{...}}}
- Ensure all outputs are read/observable (no dead storage)

## Harden Steps
- Target PDK: gf180mcuD
- Clock port: clk
- Area target: < 500×500 µm (< 0.25 mm²)
- Verify flip-flop count < 2000 (streaming architecture ensures this)
- Run through yosys synthesis, check area/timing

## Report Steps
- Document final module list, area results, timing
- Include input/output visualization (chip_input.png, chip_output.png)
- Compare RTL output vs Python golden model
- Document any deviations from plan and lessons learned