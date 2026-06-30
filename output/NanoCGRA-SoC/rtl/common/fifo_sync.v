`timescale 1ns/1ps
//////////////////////////////////////////////////////////////////////////////////
// NanoCGRA-SoC
//
// Module:
//   fifo_sync
//
// Description:
//   Parameterized synchronous FIFO.
//   - Single clock
//   - Single producer / single consumer
//   - Synthesizable
//   - Verilog-2001
//
//////////////////////////////////////////////////////////////////////////////////

module fifo_sync
#(
    parameter DATA_WIDTH = 8,
    parameter ADDR_WIDTH = 4          // DEPTH = 2^ADDR_WIDTH
)
(
    input  wire                     clk,
    input  wire                     rst_n,

    input  wire                     wr_en,
    input  wire                     rd_en,

    input  wire [DATA_WIDTH-1:0]    din,

    output reg  [DATA_WIDTH-1:0]    dout,

    output wire                     full,
    output wire                     empty,

    output wire [ADDR_WIDTH:0]      level
);

localparam DEPTH = (1 << ADDR_WIDTH);

//////////////////////////////////////////////////////////////
// Memory
//////////////////////////////////////////////////////////////

reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];

//////////////////////////////////////////////////////////////
// Pointers
//////////////////////////////////////////////////////////////

reg [ADDR_WIDTH:0] wr_ptr;
reg [ADDR_WIDTH:0] rd_ptr;

wire write_ok;
wire read_ok;

assign write_ok = wr_en & ~full;
assign read_ok  = rd_en & ~empty;

//////////////////////////////////////////////////////////////
// Level
//////////////////////////////////////////////////////////////

assign level = wr_ptr - rd_ptr;

//////////////////////////////////////////////////////////////
// Empty
//////////////////////////////////////////////////////////////

assign empty = (wr_ptr == rd_ptr);

//////////////////////////////////////////////////////////////
// Full
//////////////////////////////////////////////////////////////

assign full =
    (wr_ptr[ADDR_WIDTH]     != rd_ptr[ADDR_WIDTH]) &&
    (wr_ptr[ADDR_WIDTH-1:0] == rd_ptr[ADDR_WIDTH-1:0]);

//////////////////////////////////////////////////////////////
// Write
//////////////////////////////////////////////////////////////

always @(posedge clk) begin

    if (write_ok) begin
        mem[wr_ptr[ADDR_WIDTH-1:0]] <= din;
    end

end

//////////////////////////////////////////////////////////////
// Read
//////////////////////////////////////////////////////////////

always @(posedge clk) begin

    if (read_ok) begin
        dout <= mem[rd_ptr[ADDR_WIDTH-1:0]];
    end

end

//////////////////////////////////////////////////////////////
// Pointer Update
//////////////////////////////////////////////////////////////

always @(posedge clk or negedge rst_n) begin

    if (!rst_n) begin

        wr_ptr <= {(ADDR_WIDTH+1){1'b0}};
        rd_ptr <= {(ADDR_WIDTH+1){1'b0}};
        dout   <= {DATA_WIDTH{1'b0}};

    end
    else begin

        if (write_ok)
            wr_ptr <= wr_ptr + 1'b1;

        if (read_ok)
            rd_ptr <= rd_ptr + 1'b1;

    end

end

endmodule