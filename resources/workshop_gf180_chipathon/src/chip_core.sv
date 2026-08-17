// GF180 Chipathon Workshop — minimal core for integration testing
module chip_core (
    input wire clk,
    input wire rst_n
);

    reg [7:0] counter;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            counter <= 8'd0;
        else
            counter <= counter + 8'd1;
    end

endmodule
