// nano_controller.v — microcoded FSM sequencer.
// Mirrors golden/model/nano_controller.py.
// Streaming Sobel: each arriving pixel is shifted into the line-buffer chain;
// whenever a valid 3x3 window exists the Sobel result is latched into a
// single-entry holding register and forwarded to the UART TX. No full-frame
// buffer, no deep FIFO.
//
// BACKPRESSURE / RATE MATCHING:
// The UART RX and TX run at the same baud rate, so each UART frame is
// 10 baud periods (4340 clk). The TX FSM (uart_tx.v) supports back-to-back
// frames (STOP->START when pre-armed), giving a TX cycle of exactly 10 baud
// — the same rate at which results are produced. A single-entry holding
// register is therefore sufficient: the producer (Sobel result) and consumer
// (UART TX) are rate-matched, and the 3-pixel row-boundary gaps give the TX
// ample catch-up time. No deep FIFO is needed.
//
// FSM (TX side):
//   TX_IDLE  — if holding register full, load tx_data and pulse tx_start,
//              go to TX_WAIT.
//   TX_WAIT  — wait for tx_done, go to TX_IDLE.
//
// Pixel path (combinational, always active):
//   pixel_in    = rx_byte
//   pixel_shift = rx_valid (always, regardless of TX state)
//   col_cnt     = pixel_cnt % IMG_W
//   row_cnt     = pixel_cnt / IMG_W
//   On rx_valid: pixel_cnt increments, and if row>=2 && col>=2,
//   sobel_out is latched into the holding register.
`include "params.vh"

module nano_controller (
    input  wire             clk,
    input  wire             rst_n,
    // UART RX side
    input  wire [7:0]       rx_byte,
    input  wire             rx_valid,
    // UART TX side
    input  wire             tx_done,
    // CGRA side
    input  wire             cgra_done,
    input  wire [`DATA_W-1:0] sobel_out,
    // MMIO bus master
    output reg  [7:0]       bus_addr,
    output reg              bus_wr,
    output reg              bus_rd,
    output reg  [7:0]       bus_wdata,
    // streaming pixel path — COMBINATIONAL
    output wire [`DATA_W-1:0] pixel_in,
    output wire              pixel_shift,
    output wire [5:0]       col_cnt,
    output wire [5:0]       row_cnt,
    // CGRA control
    output reg              start_cgra,
    // UART TX control
    output reg              tx_start,
    output reg  [7:0]       tx_data,
    // status
    output reg  [7:0]       status
);

    // TX FSM states
    localparam TX_IDLE  = 2'd0;
    localparam TX_WAIT  = 2'd2;

    reg [1:0]  tx_state;
    reg [10:0] pixel_cnt;   // total pixels received (0..1023)
    reg [9:0]  out_cnt;     // results sent (0..899)

    // Single-entry holding register (replaces the former 128-deep FIFO).
    // The Sobel result is latched here when a valid window exists; the TX
    // FSM pops it at the next TX_IDLE. Because RX and TX are rate-matched
    // (both 10-baud-per-byte) and the TX supports back-to-back frames,
    // the holding register never overflows.
    reg        hold_valid;
    reg [`DATA_W-1:0] hold_data;

    // Combinational col/row for the CURRENT pixel (pre-increment).
    wire [5:0] cur_col = pixel_cnt[4:0];        // pixel_cnt % 32
    wire [5:0] cur_row = pixel_cnt[10:5];       // pixel_cnt / 32

    // Combinational pixel-path outputs: active on EVERY rx_valid.
    // This matches the golden model which accepts every pixel.
    assign pixel_in    = rx_byte;
    assign pixel_shift = rx_valid;
    assign col_cnt     = cur_col;
    assign row_cnt     = cur_row;

    // Result latch: when a valid window exists and a pixel arrives,
    // capture the Sobel result into the holding register.
    wire window_valid = (cur_row >= 6'd2) && (cur_col >= 6'd2);
    wire result_ready  = rx_valid && window_valid;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_state     <= TX_IDLE;
            pixel_cnt    <= 11'd0;
            out_cnt      <= 10'd0;
            bus_addr     <= 8'd0;
            bus_wr       <= 1'b0;
            bus_rd       <= 1'b0;
            bus_wdata    <= 8'd0;
            start_cgra   <= 1'b0;
            tx_start     <= 1'b0;
            tx_data      <= 8'd0;
            status       <= 8'd0;
            hold_valid   <= 1'b0;
            hold_data    <= 8'd0;
        end else begin
            // default pulses
            start_cgra  <= 1'b0;
            tx_start    <= 1'b0;
            bus_wr      <= 1'b0;
            bus_rd      <= 1'b0;

            // ---- Pixel acceptance (always active) ----
            if (rx_valid) begin
                pixel_cnt <= pixel_cnt + 11'd1;
            end

            // ---- Result latch into holding register ----
            if (result_ready) begin
                hold_valid <= 1'b1;
                hold_data  <= sobel_out;
            end

            // ---- TX FSM: pop holding register and transmit ----
            case (tx_state)
                TX_IDLE: begin
                    if (hold_valid) begin
                        // Pop result and start TX
                        tx_data    <= hold_data;
                        tx_start   <= 1'b1;
                        hold_valid <= 1'b0;
                        tx_state   <= TX_WAIT;
                    end
                end
                TX_WAIT: begin
                    if (tx_done) begin
                        out_cnt <= out_cnt + 10'd1;
                        if ((out_cnt + 10'd1) >= (`OUT_W * `OUT_H)) begin
                            status   <= 8'h02;  // done
                            tx_state <= TX_IDLE;
                        end else begin
                            tx_state <= TX_IDLE;
                        end
                    end
                end
                default: tx_state <= TX_IDLE;
            endcase
        end
    end

endmodule