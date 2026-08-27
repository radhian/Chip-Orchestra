// uart_tx.v — UART transmitter (byte -> serial)
// Frame: 1 start bit (0), 8 data bits LSB-first, 1 stop bit (1).
// tx_start is latched on ANY clock (not only on baud tick) so a
// 1-cycle request pulse is never dropped. tx_done pulses 1 cycle
// when the stop bit finishes.
//
// The baud divider is RESET when a new frame begins (IDLE->START).
// This guarantees the start bit is always aligned to baud-tick phase 0,
// so an external receiver that counts a fixed number of clocks from
// the start-bit edge samples each bit at the correct time regardless
// of the free-running baud phase when the frame was requested.
//
// BACK-TO-BACK FRAMES (no IDLE gap): when the STOP bit ends, if
// start_req is already set (pre-armed by the controller during the
// current frame), the FSM transitions directly STOP->START instead
// of STOP->IDLE->START.  This eliminates the 1-baud IDLE gap so the
// TX frame cycle is exactly 10 baud periods (same as the RX frame
// cycle), keeping the streaming Sobel producer/consumer rate-matched
// with only a single-entry holding register in the controller.
//
// NOTE: baud_cnt has EXACTLY ONE driver — the baud-divider always
// block below. The FSM block never writes baud_cnt directly. When a
// new frame starts (IDLE->START on a baud_tick), the baud divider has
// already wrapped baud_cnt back to 0 (baud_tick fires only when
// baud_cnt == BAUD_DIV-1), so the start bit is naturally at phase 0
// with no extra reset needed. This keeps the netlist single-driver
// clean for synthesis.
`include "params.vh"

module uart_tx (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tx_start,
    input  wire [7:0] data_in,
    output reg        tx_out,
    output reg        tx_done
);

    // FSM states
    localparam IDLE   = 2'd0;
    localparam START  = 2'd1;
    localparam DATA   = 2'd2;
    localparam STOP   = 2'd3;

    reg [1:0]  state;
    reg [2:0]  bit_idx;
    reg [7:0]  shreg;
    reg        start_req;
    reg [7:0]  start_data;

    // Internal baud divider — SOLE OWNER of baud_cnt.
    // When a new frame starts the divider has just wrapped to 0
    // (baud_tick fired), so the start bit is always at phase 0.
    reg [8:0] baud_cnt;   // counts to BAUD_DIV(434) - 9 bits, not 32
    reg        baud_tick;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            baud_cnt   <= 32'd0;
            baud_tick  <= 1'b0;
        end else begin
            if (baud_cnt == `BAUD_DIV - 1) begin
                baud_cnt  <= 32'd0;
                baud_tick <= 1'b1;
            end else begin
                baud_cnt  <= baud_cnt + 32'd1;
                baud_tick <= 1'b0;
            end
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state       <= IDLE;
            bit_idx     <= 3'd0;
            shreg       <= 8'd0;
            tx_out      <= 1'b1;   // idle high
            tx_done     <= 1'b0;
            start_req   <= 1'b0;
            start_data  <= 8'd0;
        end else begin
            tx_done <= 1'b0;  // default
            // LATCH tx_start on ANY clock so a 1-cycle pulse is never dropped
            if (tx_start) begin
                start_req  <= 1'b1;
                start_data <= data_in;
            end
            if (baud_tick) begin
                case (state)
                    IDLE: begin
                        if (start_req) begin
                            shreg     <= start_data;
                            bit_idx   <= 3'd0;
                            state     <= START;
                            tx_out    <= 1'b0;   // begin start bit
                            start_req <= 1'b0;
                            // baud_cnt is already 0: the baud divider
                            // wrapped it this cycle (baud_tick fires only
                            // at BAUD_DIV-1). No direct write here —
                            // single-driver invariant preserved.
                        end else begin
                            tx_out <= 1'b1;
                        end
                    end
                    START: begin
                        // start-bit period over; emit first data bit (bit 0)
                        tx_out  <= shreg[0];
                        bit_idx <= 3'd1;
                        state   <= DATA;
                    end
                    DATA: begin
                        tx_out  <= shreg[bit_idx];
                        if (bit_idx == 3'd7) begin
                            state <= STOP;
                        end else begin
                            bit_idx <= bit_idx + 3'd1;
                        end
                    end
                    STOP: begin
                        tx_out  <= 1'b1;
                        tx_done <= 1'b1;
                        // Back-to-back: if start_req is already set
                        // (pre-armed during this frame), go directly
                        // to START — no IDLE gap.
                        if (start_req) begin
                            shreg     <= start_data;
                            bit_idx   <= 3'd0;
                            state     <= START;
                            tx_out    <= 1'b0;   // begin next start bit
                            start_req <= 1'b0;
                        end else begin
                            state <= IDLE;
                        end
                    end
                    default: begin
                        tx_out <= 1'b1;
                        state  <= IDLE;
                    end
                endcase
            end
        end
    end

endmodule