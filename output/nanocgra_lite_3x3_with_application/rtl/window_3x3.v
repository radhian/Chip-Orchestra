// window_3x3.v — assembles a 3x3 window from 2 line buffers + current pixel.
// Mirrors golden/model/window_3x3.py.
// Uses 3 column shift registers (3-deep each) for rows N-2, N-1, N.
// On each shift_en (rising edge):
//   - Shifts all 3 column registers left, pushing new column on the right
//   - lb0_data = row N-2 pixel at current column
//   - lb1_data = row N-1 pixel at current column
//   - pixel_in = current arriving pixel (row N)
// win is COMBINATIONAL (look-ahead): it shows the window that WILL BE valid
// after the current shift, computed from pre-shift register values + new data.
// This allows the Sobel core to compute combinationally on the same cycle.
// win[0]=TL .. win[8]=BR (row-major), packed 72 bits.
`include "params.vh"

module window_3x3 (
    input  wire               clk,
    input  wire               rst_n,
    input  wire               shift_en,
    input  wire [`DATA_W-1:0] pixel_in,    // current arriving pixel (row N, col c)
    input  wire [`DATA_W-1:0] lb0_data,    // row N-2 pixel at col c
    input  wire [`DATA_W-1:0] lb1_data,    // row N-1 pixel at col c
    input  wire [5:0]         col_cnt,     // current column (0..31)
    input  wire [5:0]         row_cnt,     // current row (0..31)
    output wire [71:0]        win,         // 9 x 8-bit, row-major 0=TL..8=BR
    output wire               window_valid
);

    // 3-deep column shift registers for each row
    reg [`DATA_W-1:0] sr0_0, sr0_1, sr0_2;  // row N-2: [col c-2, col c-1, col c]
    reg [`DATA_W-1:0] sr1_0, sr1_1, sr1_2;  // row N-1
    reg [`DATA_W-1:0] sr2_0, sr2_1, sr2_2;  // row N

    // Combinational look-ahead window (next-state after shift)
    // After shift: sr[0]<=sr[1], sr[1]<=sr[2], sr[2]<=new_data
    // New window = {sr0_1_old, sr0_2_old, lb0_data,
    //               sr1_1_old, sr1_2_old, lb1_data,
    //               sr2_1_old, sr2_2_old, pixel_in}
    assign win = {sr0_1, sr0_2, lb0_data,
                  sr1_1, sr1_2, lb1_data,
                  sr2_1, sr2_2, pixel_in};

    assign window_valid = (col_cnt >= 6'd2) && (row_cnt >= 6'd2);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sr0_0 <= 8'd0; sr0_1 <= 8'd0; sr0_2 <= 8'd0;
            sr1_0 <= 8'd0; sr1_1 <= 8'd0; sr1_2 <= 8'd0;
            sr2_0 <= 8'd0; sr2_1 <= 8'd0; sr2_2 <= 8'd0;
        end else if (shift_en) begin
            // shift column registers left, push new column on the right
            sr0_0 <= sr0_1; sr0_1 <= sr0_2; sr0_2 <= lb0_data;
            sr1_0 <= sr1_1; sr1_1 <= sr1_2; sr1_2 <= lb1_data;
            sr2_0 <= sr2_1; sr2_1 <= sr2_2; sr2_2 <= pixel_in;
        end
    end

endmodule