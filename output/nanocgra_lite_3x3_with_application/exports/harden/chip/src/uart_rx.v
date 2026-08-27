// uart_rx.v — UART receiver (serial -> byte)
// Frame: 1 start bit (0), 8 data bits LSB-first, 1 stop bit (1).
// Samples at baud_tick. Detects start via falling edge (idle high -> 0).
// rx_valid pulses 1 cycle when a full byte is received.
`include "params.vh"

module uart_rx (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       rx_in,
    output reg  [7:0] rx_byte,
    output reg        rx_valid
);

    // FSM states
    localparam STOP  = 2'd0;
    localparam DATA  = 2'd1;

    reg [1:0]  state;
    reg [2:0]  bit_idx;
    reg [7:0]  shreg;
    reg        prev_line;

    // baud tick
    wire baud_tick;
    baud_gen u_bg (
        .clk(clk),
        .rst_n(rst_n),
        .baud_tick(baud_tick)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state     <= STOP;
            bit_idx   <= 3'd0;
            shreg     <= 8'd0;
            prev_line <= 1'b1;
            rx_byte   <= 8'd0;
            rx_valid  <= 1'b0;
        end else begin
            rx_valid <= 1'b0;  // default: deassert
            if (baud_tick) begin
                if (state == STOP) begin
                    // detect start bit (falling edge to 0)
                    if (prev_line == 1'b1 && rx_in == 1'b0) begin
                        state   <= DATA;
                        bit_idx <= 3'd0;
                        shreg   <= 8'd0;
                    end
                end else begin // DATA
                    // sample data bit (LSB first)
                    shreg[bit_idx] <= rx_in;
                    if (bit_idx == 3'd7) begin
                        // bit7 = rx_in (this tick), bits 6..0 = shreg[6:0] (old values)
                        rx_byte  <= {rx_in, shreg[6:0]};
                        state    <= STOP;
                        rx_valid <= 1'b1;
                    end else begin
                        bit_idx <= bit_idx + 3'd1;
                    end
                end
                prev_line <= rx_in;
            end
        end
    end

endmodule