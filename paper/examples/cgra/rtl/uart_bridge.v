//============================================================================
// uart_bridge.v  -  UART-to-internal-bus bridge (host-side bus MASTER).
//
//   NanoCGRA-Lite "opt" variant exposes only 4 pins: clk, rst_n, uart_rx,
//   uart_tx.  All host access to the internal 8-bit MMIO bus is funneled
//   through a simple 3-byte serial command protocol decoded by this bridge.
//
//   The bridge is the SINGLE master on the internal host bus. It talks to the
//   (unchanged) memory-mapped UART peripheral over that same bus:
//       * poll  UART STATUS (0x82) bit1 (rx_valid)
//       * read  UART RXDATA (0x81)   to pull an inbound byte
//       * write UART TXDATA (0x80)   to serialize a byte back to the host
//
//   Packet protocol (3 bytes, received LSB-first over UART):
//       [ CMD(1B) ] [ ADDR(1B) ] [ DATA(1B) ]
//         CMD = 0x01  WRITE : bus[ADDR] <= DATA
//         CMD = 0x02  READ  : reply DATA = bus[ADDR] serialized via UART TX
//         CMD = 0x03  RUN   : bus[START_REG] <= DATA (kick a CGRA run)
//
//   Fully synchronous, single clock domain, synchronous reset, no latches.
//============================================================================
`include "params.vh"

module uart_bridge #(
    parameter DW = `DATA_WIDTH,
    parameter AW = `ADDR_WIDTH
) (
    input  wire            clk,
    input  wire            rst_n,

    // ---- internal host-bus master port ----
    output reg  [AW-1:0]   bus_addr,
    output reg             bus_we,
    output reg             bus_re,
    output reg  [DW-1:0]   bus_wdata,
    input  wire [DW-1:0]   bus_rdata
);
    // ---- protocol command opcodes ------------------------------------
    localparam [DW-1:0] CMD_WRITE = 8'h01;
    localparam [DW-1:0] CMD_READ  = 8'h02;
    localparam [DW-1:0] CMD_RUN   = 8'h03;

    // ---- UART register addresses (from params.vh) --------------------
    localparam [AW-1:0] A_TXDATA = `UART_TXDATA;   // 0x80
    localparam [AW-1:0] A_RXDATA = `UART_RXDATA;   // 0x81
    localparam [AW-1:0] A_STATUS = `UART_STATUS;   // 0x82
    localparam [AW-1:0] A_START  = `START_REG;     // 0xA0

    // ---- bridge FSM state encoding -----------------------------------
    localparam [3:0]
        S_POLL_SET  = 4'd0,   // drive READ of UART STATUS
        S_POLL_CAP  = 4'd1,   // sample STATUS, branch on rx_valid
        S_RX_SET    = 4'd2,   // drive READ of UART RXDATA
        S_RX_CAP    = 4'd3,   // sample byte, store into packet buffer
        S_DECODE    = 4'd4,   // classify a complete 3-byte packet
        S_WR_SET    = 4'd5,   // WRITE : drive bus write to ADDR
        S_WR_DONE   = 4'd6,
        S_RD_SET    = 4'd7,   // READ  : drive bus read of ADDR
        S_RD_WAIT   = 4'd8,   // hold addr one extra cycle (SRAM read latency)
        S_RD_CAP    = 4'd9,   // capture read data
        S_TXW_SET   = 4'd10,  // drive READ of UART STATUS (tx_busy poll)
        S_TXW_CAP   = 4'd11,  // sample STATUS, wait tx_busy clear
        S_TX_SET    = 4'd12,  // WRITE captured byte to UART TXDATA
        S_TX_DONE   = 4'd13,
        S_RUN_SET   = 4'd14,  // RUN   : write START_REG
        S_RUN_DONE  = 4'd15;

    reg [3:0]     state;
    reg [1:0]     byte_idx;      // 0..2 packet byte index
    reg [DW-1:0]  cmd_reg, addr_reg, data_reg;
    reg [DW-1:0]  rd_cap;

    always @(posedge clk) begin
        if (!rst_n) begin
            state     <= S_POLL_SET;
            byte_idx  <= 2'd0;
            cmd_reg   <= {DW{1'b0}};
            addr_reg  <= {DW{1'b0}};
            data_reg  <= {DW{1'b0}};
            rd_cap    <= {DW{1'b0}};
            bus_addr  <= {AW{1'b0}};
            bus_we    <= 1'b0;
            bus_re    <= 1'b0;
            bus_wdata <= {DW{1'b0}};
        end else begin
            // default: deassert strobes every cycle (pulse them in states)
            bus_we <= 1'b0;
            bus_re <= 1'b0;

            case (state)
                // ---- poll UART STATUS for rx_valid ------------------
                S_POLL_SET: begin
                    bus_addr <= A_STATUS;
                    bus_re   <= 1'b1;
                    state    <= S_POLL_CAP;
                end
                S_POLL_CAP: begin
                    // bus_rdata valid this cycle (1-clk registered read)
                    if (bus_rdata[1])          // rx_valid
                        state <= S_RX_SET;
                    else
                        state <= S_POLL_SET;
                end

                // ---- pull one inbound byte from UART RXDATA ---------
                S_RX_SET: begin
                    bus_addr <= A_RXDATA;
                    bus_re   <= 1'b1;
                    state    <= S_RX_CAP;
                end
                S_RX_CAP: begin
                    case (byte_idx)
                        2'd0: cmd_reg  <= bus_rdata;
                        2'd1: addr_reg <= bus_rdata;
                        default: data_reg <= bus_rdata;
                    endcase
                    if (byte_idx == 2'd2) begin
                        byte_idx <= 2'd0;
                        state    <= S_DECODE;
                    end else begin
                        byte_idx <= byte_idx + 2'd1;
                        state    <= S_POLL_SET;   // wait for next byte
                    end
                end

                // ---- classify a full 3-byte packet ------------------
                S_DECODE: begin
                    case (cmd_reg)
                        CMD_WRITE: state <= S_WR_SET;
                        CMD_READ:  state <= S_RD_SET;
                        CMD_RUN:   state <= S_RUN_SET;
                        default:   state <= S_POLL_SET; // unknown -> drop
                    endcase
                end

                // ---- WRITE : bus[ADDR] <= DATA ----------------------
                S_WR_SET: begin
                    bus_addr  <= addr_reg;
                    bus_wdata <= data_reg;
                    bus_we    <= 1'b1;
                    state     <= S_WR_DONE;
                end
                S_WR_DONE: state <= S_POLL_SET;

                // ---- READ : capture bus[ADDR], echo via UART TX -----
                S_RD_SET: begin
                    bus_addr <= addr_reg;
                    bus_re   <= 1'b1;
                    state    <= S_RD_WAIT;
                end
                S_RD_WAIT: begin
                    // hold addr one extra cycle so registered SRAM dout settles;
                    // harmless for combinational UART reads.
                    bus_addr <= addr_reg;
                    state    <= S_RD_CAP;
                end
                S_RD_CAP: begin
                    rd_cap <= bus_rdata;         // read data now valid
                    state  <= S_TXW_SET;
                end
                S_TXW_SET: begin
                    // drive a read of UART STATUS; data valid next cycle
                    bus_addr <= A_STATUS;
                    bus_re   <= 1'b1;
                    state    <= S_TXW_CAP;
                end
                S_TXW_CAP: begin
                    // sample STATUS; wait until tx_busy (bit0) clear
                    if (!bus_rdata[0])
                        state <= S_TX_SET;
                    else
                        state <= S_TXW_SET;
                end
                S_TX_SET: begin
                    bus_addr  <= A_TXDATA;
                    bus_wdata <= rd_cap;
                    bus_we    <= 1'b1;
                    state     <= S_TX_DONE;
                end
                S_TX_DONE: state <= S_POLL_SET;

                // ---- RUN : write START_REG --------------------------
                S_RUN_SET: begin
                    bus_addr  <= A_START;
                    bus_wdata <= data_reg;
                    bus_we    <= 1'b1;
                    state     <= S_RUN_DONE;
                end
                S_RUN_DONE: state <= S_POLL_SET;

                default: state <= S_POLL_SET;
            endcase
        end
    end
endmodule
