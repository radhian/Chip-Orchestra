//============================================================================
// sram.v  -  128 x 8-bit single-port synchronous SRAM (register-array model)
// Synchronous reset, single read/write port, synthesizable.
//============================================================================
`include "params.vh"

module sram #(
    parameter DW = `DATA_WIDTH,
    parameter AW = `SRAM_AW,
    parameter DEPTH = `SRAM_SIZE
) (
    input  wire            clk,
    input  wire            rst_n,
    input  wire [AW-1:0]   addr,
    input  wire            we,
    input  wire [DW-1:0]   din,
    output reg  [DW-1:0]   dout
);
    integer i;
    reg [DW-1:0] mem [0:DEPTH-1];

    // Single synchronous process: synchronous reset, single write port,
    // registered read (read-after-write returns old data - classic 1-port).
    always @(posedge clk) begin
        if (!rst_n) begin
            for (i = 0; i < DEPTH; i = i + 1)
                mem[i] <= {DW{1'b0}};
            dout <= {DW{1'b0}};
        end else begin
            if (we)
                mem[addr] <= din;
            dout <= mem[addr];
        end
    end
endmodule
