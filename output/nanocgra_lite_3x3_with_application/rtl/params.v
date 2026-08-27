// rtl/params.v — Shared parameters for nano CGRA 3x3 Sobel filter accelerator.
// Mirrors golden/model/params.py.  All arithmetic is integer / fixed-point.
// Pixel data is unsigned 8-bit (0..255).  Sobel intermediate sums are signed
// 9-bit (-510..+510); final magnitude |Gx|+|Gy| is saturated to unsigned 8-bit.
//
// This is a parameters-only module: it has no ports and no logic.  Other
// modules reference it via `include "params.vh"` OR by hierarchical parameter
// override.  To keep a single source of truth usable by every module, the
// values are also emitted as `define macros so any file can `include this
// file directly.  (No frame stores — streaming design.)
//
// NOTE: This file is valid Verilog-2001.  It defines a parameter module AND
// `define macros.  Modules that prefer parameters can instantiate `params`
// and use its localparams; modules that prefer macros can `include this file.

`ifndef PARAMS_V
`define PARAMS_V

// ---- Clock / UART ----
`define CLK_FREQ    32'd50_000_000   // 50 MHz
`define BAUD_RATE   32'd115_200      // UART baud
`define DATA_W      8                // pixel / data width (bits)

// ---- Image geometry ----
`define IMG_W       32               // image width  (pixels)
`define IMG_H       32               // image height (pixels)
`define OUT_W       30               // output width  = IMG_W - 2
`define OUT_H       30               // output height = IMG_H - 2
`define LINE_BUF_W  32               // line buffer width = one row

// ---- MMIO address map (8-bit address space) ----
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

// ---- Sobel kernel weights (Gx, Gy) per PE position (row-major: 0..8) ----
//   PE0 top-left, PE1 top-mid, PE2 top-right
//   PE3 mid-left, PE4 center,  PE5 mid-right
//   PE6 bot-left, PE7 bot-mid, PE8 bot-right
// Gx
`define SOBEL_GX_P0  -1
`define SOBEL_GX_P1   0
`define SOBEL_GX_P2   1
`define SOBEL_GX_P3  -2
`define SOBEL_GX_P4   0
`define SOBEL_GX_P5   2
`define SOBEL_GX_P6  -1
`define SOBEL_GX_P7   0
`define SOBEL_GX_P8   1
// Gy
`define SOBEL_GY_P0  -1
`define SOBEL_GY_P1  -2
`define SOBEL_GY_P2  -1
`define SOBEL_GY_P3   0
`define SOBEL_GY_P4   0
`define SOBEL_GY_P5   0
`define SOBEL_GY_P6   1
`define SOBEL_GY_P7   2
`define SOBEL_GY_P8   1

// ---- Bit widths derived from DATA_W ----
`define DATA_W_M1    7               // DATA_W-1
`define SOBEL_SUM_W  9               // signed 9-bit for Gx/Gy sums
`define SOBEL_SUM_W_M1 8

// ---- CGRA grid ----
`define CGRA_ROWS    3
`define CGRA_COLS    3
`define CGRA_NPE     9               // 3x3 = 9 PEs

// ---- SRAM ----
`define SRAM_DEPTH   32              // 32 bytes

module params (
    // Parameter-only module: no ports.  Values exposed as localparams below
    // for modules that instantiate `params` and reference its members via
    // hierarchical names or parameter inheritance.
);

    // Clock / UART
    localparam [31:0] CLK_FREQ   = 32'd50_000_000;
    localparam [31:0] BAUD_RATE  = 32'd115_200;
    localparam integer DATA_W    = 8;

    // Image geometry
    localparam integer IMG_W      = 32;
    localparam integer IMG_H      = 32;
    localparam integer OUT_W      = 30;
    localparam integer OUT_H      = 30;
    localparam integer LINE_BUF_W = 32;

    // MMIO address map
    localparam [7:0] ADDR_SRAM_BASE     = 8'h00;
    localparam [7:0] ADDR_UART_TXDATA   = 8'h80;
    localparam [7:0] ADDR_UART_RXDATA   = 8'h81;
    localparam [7:0] ADDR_UART_STATUS   = 8'h82;
    localparam [7:0] ADDR_UART_CTRL     = 8'h83;
    localparam [7:0] ADDR_CGRA_CFG_BASE = 8'h90;
    localparam [7:0] ADDR_CGRA_OPA      = 8'h99;
    localparam [7:0] ADDR_CGRA_OPB      = 8'h9A;
    localparam [7:0] ADDR_CGRA_RES      = 8'h9B;
    localparam [7:0] ADDR_START         = 8'hA0;
    localparam [7:0] ADDR_STATUS        = 8'hA1;

    // Sobel kernel weights — Gx (row-major 0..8)
    localparam signed [3:0] SOBEL_GX_P0 = -4'sd1;
    localparam signed [3:0] SOBEL_GX_P1 =  4'sd0;
    localparam signed [3:0] SOBEL_GX_P2 =  4'sd1;
    localparam signed [3:0] SOBEL_GX_P3 = -4'sd2;
    localparam signed [3:0] SOBEL_GX_P4 =  4'sd0;
    localparam signed [3:0] SOBEL_GX_P5 =  4'sd2;
    localparam signed [3:0] SOBEL_GX_P6 = -4'sd1;
    localparam signed [3:0] SOBEL_GX_P7 =  4'sd0;
    localparam signed [3:0] SOBEL_GX_P8 =  4'sd1;

    // Sobel kernel weights — Gy (row-major 0..8)
    localparam signed [3:0] SOBEL_GY_P0 = -4'sd1;
    localparam signed [3:0] SOBEL_GY_P1 = -4'sd2;
    localparam signed [3:0] SOBEL_GY_P2 = -4'sd1;
    localparam signed [3:0] SOBEL_GY_P3 =  4'sd0;
    localparam signed [3:0] SOBEL_GY_P4 =  4'sd0;
    localparam signed [3:0] SOBEL_GY_P5 =  4'sd0;
    localparam signed [3:0] SOBEL_GY_P6 =  4'sd1;
    localparam signed [3:0] SOBEL_GY_P7 =  4'sd2;
    localparam signed [3:0] SOBEL_GY_P8 =  4'sd1;

    // Derived bit widths
    localparam integer SOBEL_SUM_W = 9;   // signed 9-bit for Gx/Gy sums

    // CGRA grid
    localparam integer CGRA_ROWS = 3;
    localparam integer CGRA_COLS = 3;
    localparam integer CGRA_NPE  = 9;

    // SRAM
    localparam integer SRAM_DEPTH = 32;

endmodule

`endif // PARAMS_V