// params.vh — shared parameters for nano_cgra_3x3_sobel_accelerator_v4
// Verilog-2001 only. Included with `include "params.vh" in every file.

`ifndef PARAMS_VH
`define PARAMS_VH

// Clock / UART
`define CLK_FREQ    32'd50_000_000   // 50 MHz
`define BAUD_RATE   32'd115_200      // UART baud
`define DATA_W      8                // pixel/data width (bits)

// Image geometry
`define IMG_W       32               // image width  (pixels)
`define IMG_H       32               // image height (pixels)
`define OUT_W       30               // output width  = IMG_W - 2
`define OUT_H       30               // output height = IMG_H - 2
`define LINE_BUF_W  32               // line buffer width = IMG_W

// Baud divider = CLK_FREQ / BAUD_RATE  (50e6 / 115200 = 434)
`define BAUD_DIV    32'd434

// MMIO Address Map (8-bit address space)
`define ADDR_SRAM_BASE      8'h00    // 0x00-0x1F : SRAM (32 B)
`define ADDR_UART_TXDATA    8'h80
`define ADDR_UART_RXDATA    8'h81
`define ADDR_UART_STATUS    8'h82
`define ADDR_UART_CTRL      8'h83
`define ADDR_CGRA_CFG_BASE  8'h90    // 0x90-0x98 : PE config (9 PEs)
`define ADDR_CGRA_OPA       8'h99
`define ADDR_CGRA_OPB       8'h9A
`define ADDR_CGRA_RES       8'h9B
`define ADDR_START          8'hA0
`define ADDR_STATUS         8'hA1    // {6'b0, done, busy}

// Sobel kernel weights (Gx, Gy) per PE position (row-major: 0..8)
//   PE0 top-left, PE1 top-mid, PE2 top-right
//   PE3 mid-left, PE4 center,  PE5 mid-right
//   PE6 bot-left, PE7 bot-mid, PE8 bot-right
// Gx = [-1, 0,+1, -2, 0,+2, -1, 0,+1]
// Gy = [-1,-2,-1,  0, 0, 0, +1,+2,+1]

`endif