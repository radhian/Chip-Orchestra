# Design Notes — nano_cgra_3x3_sobel_accelerator_v4

## Build Contract

This document is the authoritative specification the RTL generator follows.
Every module, port, and interface signal is defined here.

## Top Module
**`nano_cgra_3x3_sobel_accelerator_v4`** — instantiated as the top-level chip.

### Top-Level Ports
| Port | Direction | Width | Description |
|------|-----------|-------|-------------|
| `clk` | input | 1 | System clock (50 MHz) |
| `rst_n` | input | 1 | Active-low synchronous reset |
| `data_i` | input | 1 | UART RX serial input (from host) |
| `data_o` | output | 1 | UART TX serial output (to host) |

## Module Map

| Module | File | Role | Key Ports |
|--------|------|------|-----------|
| `reset_sync` | `rtl/reset_sync.v` | Power-on + sync reset generator | `clk`, `rst_async_n` → `rst_n` |
| `uart_rx` | `rtl/uart_rx.v` | UART receiver (serial→byte) | `clk`, `rst_n`, `rx_in` → `rx_byte[7:0]`, `rx_valid` |
| `uart_tx` | `rtl/uart_tx.v` | UART transmitter (byte→serial) | `clk`, `rst_n`, `tx_start`, `data_in[7:0]` → `tx_out`, `tx_done` |
| `baud_gen` | `rtl/baud_gen.v` | Baud rate tick generator | `clk`, `rst_n` → `baud_tick` |
| `line_buffer` | `rtl/line_buffer.v` | 32-byte row shift register | `clk`, `rst_n`, `shift_en`, `pixel_in[7:0]` → `tap0[7:0]`, `tap1[7:0]`, `tap2[7:0]` (3 taps for window column) |
| `window_3x3` | `rtl/window_3x3.v` | 3×3 window assembler from 2 line buffers + current pixel | `clk`, `rst_n`, `pixel_in[7:0]`, `shift_en` → `win[0:8]` (9×8b), `window_valid` |
| `pe` | `rtl/pe.v` | Single Processing Element (8-bit ALU) | `clk`, `rst_n`, `cfg[2:0]`, `opa[7:0]`, `opb[7:0]`, `cin[7:0]` → `result[7:0]`, `cout[7:0]` |
| `cgra_3x3` | `rtl/cgra_3x3.v` | 3×3 PE mesh array with N/W/E/S interfaces | `clk`, `rst_n`, `win[0:8]` (72b), `cfg[8:0]`, `start` → `sobel_out[7:0]`, `done` |
| `sobel_core` | `rtl/sobel_core.v` | Sobel Gx/Gy shift-add compute + magnitude saturate | `win[0:8]` (72b) → `sobel_out[7:0]` |
| `sram_32b` | `rtl/sram_32b.v` | 32-byte single-port SRAM | `clk`, `addr[4:0]`, `wr_en`, `data_in[7:0]` → `data_out[7:0]` |
| `mmio_bus` | `rtl/mmio_bus.v` | 8-bit MMIO interconnect / address decoder | `clk`, `rst_n`, `mst_addr[7:0]`, `mst_wr`, `mst_rd`, `mst_wdata[7:0]` → `mst_rdata[7:0]`, slave select lines |
| `nano_controller` | `rtl/nano_controller.v` | Microcoded FSM sequencer (command decode, addr gen, loop counter, status) | `clk`, `rst_n`, `rx_byte[7:0]`, `rx_valid`, `tx_done`, `cgra_done` → `bus_addr[7:0]`, `bus_wr`, `bus_wdata[7:0]`, `pixel_feed`, `start_cgra`, `tx_start`, `tx_data[7:0]`, `status[7:0]` |
| `nano_cgra_3x3_sobel_accelerator_v4` | `rtl/nano_cgra_3x3_sobel_accelerator_v4.v` | TOP module integrating all blocks | `clk`, `rst_n`, `data_i`, `data_o` |

## Shared Parameters (`rtl/params.vh`)
```verilog
`define CLK_FREQ    50000000   // 50 MHz
`define BAUD_RATE   115200     // UART baud
`define DATA_W      8          // pixel/data width
`define IMG_W       32         // image width
`define IMG_H       32         // image height
`define OUT_W       30         // output width (IMG_W - 2)
`define OUT_H       30         // output height (IMG_H - 2)
`define LINE_BUF_W  32         // line buffer width = IMG_W

// MMIO Address Map
`define ADDR_SRAM_BASE    8'h00   // 0x00-0x1F: SRAM (32 B)
`define ADDR_UART_TXDATA  8'h80
`define ADDR_UART_RXDATA  8'h81
`define ADDR_UART_STATUS  8'h82
`define ADDR_UART_CTRL    8'h83
`define ADDR_CGRA_CFG_BASE 8'h90  // 0x90-0x98: PE config (9 PEs)
`define ADDR_CGRA_OPA     8'h99
`define ADDR_CGRA_OPB     8'h9A
`define ADDR_CGRA_RES     8'h9B
`define ADDR_START        8'hA0
`define ADDR_STATUS       8'hA1   // {6'b0, done, busy}
```

## Inter-Module Interfaces

### 1. UART RX → NanoController
| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| `rx_byte[7:0]` | 8 | rx→ctrl | Received byte |
| `rx_valid` | 1 | rx→ctrl | Pulse: byte valid for 1 cycle |

### 2. NanoController → UART TX
| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| `tx_data[7:0]` | 8 | ctrl→tx | Byte to transmit |
| `tx_start` | 1 | ctrl→tx | Pulse: start transmission |
| `tx_done` | 1 | tx→ctrl | Pulse: transmission complete |

### 3. NanoController → MMIO Bus (master)
| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| `bus_addr[7:0]` | 8 | ctrl→bus | MMIO address |
| `bus_wr` | 1 | ctrl→bus | Write strobe |
| `bus_rd` | 1 | ctrl→bus | Read strobe |
| `bus_wdata[7:0]` | 8 | ctrl→bus | Write data |
| `bus_rdata[7:0]` | 8 | bus→ctrl | Read data return |

### 4. MMIO Bus → Slaves (decoded selects)
| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| `sram_sel` | 1 | bus→sram | SRAM selected |
| `uart_sel` | 1 | bus→uart | UART regs selected |
| `cgra_sel` | 1 | bus→cgra | CGRA config selected |
| `sram_addr[4:0]` | 5 | bus→sram | SRAM address (lower 5 bits) |
| `sram_wr_en` | 1 | bus→sram | SRAM write enable |
| `sram_wdata[7:0]` | 8 | bus→sram | SRAM write data |
| `sram_rdata[7:0]` | 8 | sram→bus | SRAM read data |

### 5. NanoController → Line Buffer / Window (streaming pixel path)
| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| `pixel_in[7:0]` | 8 | ctrl→linebuf | Incoming pixel from UART RX |
| `pixel_shift_en` | 1 | ctrl→linebuf | Shift enable (new pixel arrives) |
| `col_cnt[5:0]` | 6 | ctrl→window | Column counter (0..31) |
| `row_cnt[5:0]` | 6 | ctrl→window | Row counter (0..31) |

### 6. Line Buffers → Window 3×3
| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| `lb0_data[7:0]` | 8 | lb0→win | Row N-2 pixel at current column |
| `lb1_data[7:0]` | 8 | lb1→win | Row N-1 pixel at current column |
| `cur_pixel[7:0]` | 8 | ctrl→win | Current arriving pixel (row N) |

### 7. Window 3×3 → CGRA / Sobel Core
| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| `win[0:8]` | 72 | win→cgra | 3×3 window: win[0]=top-left ... win[8]=bot-right |
| `window_valid` | 1 | win→ctrl | Window is valid (rows≥2, cols≥2) |

### 8. CGRA → NanoController (status)
| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| `sobel_out[7:0]` | 8 | cgra→ctrl | Computed Sobel result byte |
| `cgra_done` | 1 | cgra→ctrl | Pulse: result valid |
| `cgra_busy` | 1 | cgra→ctrl | CGRA currently computing |

### 9. Reset Logic
| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| `rst_n` | 1 | reset→all | Synchronized active-low reset to all modules |

## NanoController FSM States
| State | Description |
|-------|-------------|
| `S_IDLE` | Wait for first byte from UART |
| `S_RECV` | Receive 32×32=1024 pixels, feed to line buffer chain; after row 2+, assemble windows and compute Sobel |
| `S_COMPUTE` | CGRA computes Sobel for current window (1-cycle combinational or pipelined) |
| `S_TX_RESULT` | Send result byte via UART TX |
| `S_NEXT` | Advance to next window position; if all 30×30 done, go to S_IDLE |

### Streaming Detail
The controller does NOT buffer the full frame. As each pixel arrives via UART:
1. Pixel is shifted into line_buffer[0] (which shifts old data to line_buffer[1])
2. After 2 full rows have been received (row_cnt ≥ 2), and for each column ≥ 2,
   the window_3x3 module assembles a valid 3×3 window
3. The CGRA/sobel_core computes the Sobel result combinationally
4. The result is immediately sent to uart_tx
5. This overlaps input reception with output transmission — fully streaming

## CGRA PE Configuration (Sobel Mapping)
Each of the 9 PEs corresponds to one position in the 3×3 window:
- **PE0** (top-left):    weight = -1 (Gx) / -1 (Gy)
- **PE1** (top-mid):     weight =  0 (Gx) / -2 (Gy)
- **PE2** (top-right):   weight = +1 (Gx) / -1 (Gy)
- **PE3** (mid-left):    weight = -2 (Gx) /  0 (Gy)
- **PE4** (center):      weight =  0 (Gx) /  0 (Gy)
- **PE5** (mid-right):   weight = +2 (Gx) /  0 (Gy)
- **PE6** (bot-left):    weight = -1 (Gx) / +1 (Gy)
- **PE7** (bot-mid):     weight =  0 (Gx) / +2 (Gy)
- **PE8** (bot-right):   weight = +1 (Gx) / +1 (Gy)

Each PE multiplies its window pixel by its configured weight (shift-add for ±1/±2),
then the array sums all PE outputs for Gx and Gy separately.
Final output = min(|Gx| + |Gy|, 255).

## Area Budget Tracking
| Storage Element | Bits | Flip-Flops |
|----------------|------|------------|
| Line buffer 0 (32 bytes) | 256 | 256 |
| Line buffer 1 (32 bytes) | 256 | 256 |
| 3×3 window registers | 72 | 72 |
| UART RX registers | ~30 | ~30 |
| UART TX registers | ~20 | ~20 |
| NanoController FSM + counters | ~50 | ~50 |
| CGRA PE config registers (9×3) | 27 | 27 |
| SRAM (32 bytes, modeled as reg array) | 256 | 256* |
| Misc pipeline/status | ~30 | ~30 |
| **Total** | **~997** | **~997** |

*SRAM may be implemented as flip-flop array for small 32B size, or as SRAM macro.
Either way, total is well under 2000 FF budget and < 0.25 mm² target.

## Input Data Preparation (Testbench)
- Source: `context/uploads/Screenshot_from_2026-07-14_16-24-31.png` (highway scene)
- Framing: WHOLE image bilinear-downscaled to 32×32 grayscale (no crop) — road surface, lane markings and horizon fill the frame. This is what context/chip_input_grid.json and rtl/sobel_input.mem actually contain (verified identical); the earlier (x=20, y=340) crop plan was NOT used.
- Convert to grayscale: Y = 0.299R + 0.587G + 0.114B, rounded to 8-bit
- Save as `rtl/sobel_input.mem` — 1024 hex bytes, one per line ($readmemh)
- Golden model: Python Sobel on same crop → `rtl/sobel_golden.mem` (900 bytes)
- Visualize: `waves/chip_input.png` (input 32×32), `waves/chip_output.png` (output 30×30)

## Key Design Rules Enforced
1. **Verilog-2001 only** — no SystemVerilog (no `logic`, `always_ff`, typedefs, interfaces)
2. **One driver per signal** — no reg assigned from two always blocks
3. **Unpacked array reset** — use for-loop, never `mem <= 0`
4. **Replication** — double braces `{N{...}}`
5. **No full-frame buffer** — streaming through line buffers only
6. **Sobel weights as shifts+adds** — no multipliers for ±1/±2 coefficients
7. **All storage observable** — every buffer read through a port
8. **Serial I/O streaming** — emit results as computed, no output frame buffer