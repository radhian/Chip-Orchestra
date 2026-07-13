//============================================================================
// bus_decoder.v  -  8-bit MMIO address decoder + slave read-data mux.
//   Pure combinational, every output assigned in every branch (no latches).
//============================================================================
`include "params.vh"

module bus_decoder #(
    parameter DW = `DATA_WIDTH,
    parameter AW = `ADDR_WIDTH
) (
    input  wire [AW-1:0]   addr,

    // slave select strobes
    output wire            sel_sram,
    output wire            sel_uart,
    output wire            sel_cgra,
    output wire            sel_start,
    output wire            sel_status,

    // read-data sources from slaves
    input  wire [DW-1:0]   sram_rdata,
    input  wire [DW-1:0]   uart_rdata,
    input  wire [DW-1:0]   status_rdata,

    // muxed read data back to the master
    output reg  [DW-1:0]   rdata
);
    assign sel_sram   = (addr <= `SRAM_HI);
    assign sel_uart   = (addr >= `UART_LO) && (addr <= `UART_HI);
    assign sel_cgra   = (addr >= `CGRA_LO) && (addr <= `CGRA_HI);
    assign sel_start  = (addr == `START_REG);
    assign sel_status = (addr == `STATUS_REG);

    always @(*) begin
        if (sel_sram)        rdata = sram_rdata;
        else if (sel_uart)   rdata = uart_rdata;
        else if (sel_status) rdata = status_rdata;
        else                 rdata = {DW{1'b0}};
    end
endmodule
