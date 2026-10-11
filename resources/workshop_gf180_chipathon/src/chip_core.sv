// GF180 Chipathon Workshop — minimal core for integration testing.
// The counter drives an observable output (dout) so synthesis keeps the
// logic; without an output port the whole core is optimised away and
// OpenROAD.GlobalPlacement fails with "No placeable instances".
module chip_core (
    input  wire clk,
    input  wire rst_n,
    output wire dout
);

    reg [7:0] counter;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            counter <= 8'd0;
        else
            counter <= counter + 8'd1;
    end

    assign dout = counter[7];

endmodule
