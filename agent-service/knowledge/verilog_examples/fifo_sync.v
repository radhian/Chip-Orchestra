// Single-clock synchronous FIFO with full/empty flags.
module fifo_sync #(parameter DW = 8, parameter AW = 4) (
    input              clk, input rst,
    input              wr_en, input [DW-1:0] din,  output full,
    input              rd_en, output reg [DW-1:0] dout, output empty
);
    localparam DEPTH = (1<<AW);
    reg [DW-1:0] mem [0:DEPTH-1];
    reg [AW:0] wptr, rptr;
    wire [AW-1:0] wa = wptr[AW-1:0], ra = rptr[AW-1:0];
    assign empty = (wptr == rptr);
    assign full  = (wptr[AW] != rptr[AW]) && (wa == ra);
    always @(posedge clk) begin
        if (rst) begin wptr <= 0; rptr <= 0; end
        else begin
            if (wr_en && !full)  begin mem[wa] <= din; wptr <= wptr + 1'b1; end
            if (rd_en && !empty) begin dout <= mem[ra]; rptr <= rptr + 1'b1; end
        end
    end
endmodule
