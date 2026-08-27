// line_buffer.v — 32-byte row delay line.
//
// The chip instantiates this with wr_col and rd_col tied to THE SAME signal
// (col_cnt): at column c it reads the pixel stored for column c one row
// earlier, then overwrites that slot with the current row's pixel. That is a
// read-before-write DELAY LINE, not a random-access memory — the address only
// ever walks 0..W-1 and repeats.
//
// Implemented as a RAM it cost 1017 cells for 256 bits of storage: a 32-way
// write decoder plus a 32:1 read multiplexer on every one of the 8 bits, i.e.
// ~75% of the module was addressing hardware that could never be used for
// anything but a sequential walk. As a shift register the same behaviour costs
// 256 cells — one flip-flop per stored bit and nothing else.
//
// The address ports are RETAINED so the top level needs no rewiring; they are
// intentionally unused. This is only equivalent while col_cnt is a plain
// incrementing counter driving both ports, which is how the top wires it.
`include "params.vh"

module line_buffer (
    input  wire                       clk,
    input  wire                       rst_n,
    input  wire                       shift_en,
    input  wire [`DATA_W-1:0]         pixel_in,
    input  wire [5:0]                 wr_col,   // unused: see header
    input  wire [5:0]                 rd_col,   // unused: see header
    output wire [`DATA_W-1:0]         rd_data   // pixel from LINE_BUF_W samples ago
);

    reg [`DATA_W-1:0] sr [0:`LINE_BUF_W-1];
    integer i;

    // The value leaving the chain is the pixel written LINE_BUF_W shifts ago —
    // exactly what mem[rd_col] returned when rd_col == wr_col.
    assign rd_data = sr[`LINE_BUF_W-1];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < `LINE_BUF_W; i = i + 1)
                sr[i] <= {`DATA_W{1'b0}};
        end else if (shift_en) begin
            for (i = `LINE_BUF_W-1; i > 0; i = i - 1)
                sr[i] <= sr[i-1];
            sr[0] <= pixel_in;
        end
    end

endmodule
