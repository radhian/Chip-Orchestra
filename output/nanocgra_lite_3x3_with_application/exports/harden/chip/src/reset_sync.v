// reset_sync.v — power-on + synchronous reset generator
// 2-flop synchronizer: rst_n deasserts synchronously after rst_async_n high.
`include "params.vh"

module reset_sync (
    input  wire clk,
    input  wire rst_async_n,
    output wire rst_n
);

    reg sync0;
    reg sync1;

    always @(posedge clk or negedge rst_async_n) begin
        if (!rst_async_n) begin
            sync0 <= 1'b0;
            sync1 <= 1'b0;
        end else begin
            sync0 <= 1'b1;
            sync1 <= sync0;
        end
    end

    assign rst_n = sync1;

endmodule