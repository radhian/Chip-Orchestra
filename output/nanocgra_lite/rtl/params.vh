//============================================================================
// params.vh  -  Single source of truth for NanoCGRA-Lite
// GF180MCU, synthesizable Verilog-2001, no latches, no tri-state.
//============================================================================
`ifndef NANOCGRA_LITE_PARAMS_VH
`define NANOCGRA_LITE_PARAMS_VH

`timescale 1ns / 1ps

// ---- Global data / address widths (parameterized) ------------------------
`define DATA_WIDTH   8
`define ADDR_WIDTH   8

// ---- Memory sizing --------------------------------------------------------
`define SRAM_SIZE    128          // 128 bytes, single-port
`define SRAM_AW      7            // log2(128) address bits into the array

// ---- PE array geometry ----------------------------------------------------
`define PE_ROWS      2
`define PE_COLS      2
`define PE_TOTAL     4

// ---- Memory map (byte addresses) -----------------------------------------
`define SRAM_LO      8'h00
`define SRAM_HI      8'h7F
`define UART_LO      8'h80
`define UART_HI      8'h83
`define UART_TXDATA  8'h80
`define UART_RXDATA  8'h81
`define UART_STATUS  8'h82
`define UART_CTRL    8'h83
`define CGRA_LO      8'h90
`define CGRA_HI      8'h97
`define CGRA_CFG0    8'h90   // PE(0,0) config
`define CGRA_CFG1    8'h91   // PE(0,1) config
`define CGRA_CFG2    8'h92   // PE(1,0) config
`define CGRA_CFG3    8'h93   // PE(1,1) config
`define CGRA_OPA     8'h94   // operand-A SRAM source address
`define CGRA_OPB     8'h95   // operand-B SRAM source address
`define CGRA_RES     8'h96   // result SRAM destination address
`define CGRA_RSVD    8'h97   // reserved
`define START_REG    8'hA0
`define STATUS_REG   8'hA1

// ---- PE ALU / AU opcodes (cfg_reg[2:0]) ----------------------------------
`define OP_ADD       3'd0
`define OP_SUB       3'd1
`define OP_AND       3'd2
`define OP_OR        3'd3
`define OP_XOR       3'd4
`define OP_MUL       3'd5    // 8x8 multiplier, low byte
`define OP_MAC       3'd6    // multiply-accumulate
`define OP_PASS      3'd7    // pass local register

// ---- PE operand-B routing select (cfg_reg[4:3]) --------------------------
`define SEL_N        2'd0
`define SEL_S        2'd1
`define SEL_E        2'd2
`define SEL_W        2'd3

// ---- Controller FSM state encoding (one source of truth) -----------------
`define ST_IDLE      3'd0
`define ST_RD_A      3'd1
`define ST_RD_B      3'd2
`define ST_LOAD      3'd3
`define ST_EXEC      3'd4
`define ST_STORE     3'd5
`define ST_DONE      3'd6

// ---- CGRA status byte (read at STATUS_REG) -------------------------------
//  bit0 = busy, bit1 = done
`define STAT_BUSY    8'h01
`define STAT_DONE    8'h02

// ---- High-level controller status codes ----------------------------------
`define STATUS_IDLE      8'h00
`define STATUS_CONFIG    8'h01
`define STATUS_EXEC      8'h02
`define STATUS_COMPLETE  8'h03

`endif // NANOCGRA_LITE_PARAMS_VH
