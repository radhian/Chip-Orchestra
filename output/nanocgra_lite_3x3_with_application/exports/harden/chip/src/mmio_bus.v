// mmio_bus.v — 8-bit MMIO interconnect / address decoder.
// Mirrors golden/model/mmio_bus.py — COMBINATIONAL decode.
// Address map:
//   0x00-0x1F : SRAM
//   0x80-0x83 : UART regs
//   0x90-0x9B : CGRA config/operands
//   0xA0      : START
//   0xA1      : STATUS
`include "params.vh"

module mmio_bus (
    input  wire             clk,
    input  wire             rst_n,
    // master side
    input  wire [7:0]       mst_addr,
    input  wire             mst_wr,
    input  wire             mst_rd,
    input  wire [7:0]       mst_wdata,
    output reg  [7:0]       mst_rdata,
    // slave selects
    output reg              sram_sel,
    output reg              uart_sel,
    output reg              cgra_sel,
    // SRAM side
    output reg  [4:0]       sram_addr,
    output reg              sram_wr_en,
    output reg  [7:0]       sram_wdata,
    input  wire [7:0]       sram_rdata,
    // UART side
    input  wire [7:0]       uart_rdata,
    // CGRA side
    input  wire [7:0]       cgra_rdata
);

    wire [7:0] a = mst_addr;

    // Combinational decode — matches golden model (no registers)
    always @(*) begin
        if (!rst_n) begin
            mst_rdata  = 8'd0;
            sram_sel   = 1'b0;
            uart_sel   = 1'b0;
            cgra_sel   = 1'b0;
            sram_addr  = 5'd0;
            sram_wr_en = 1'b0;
            sram_wdata = 8'd0;
        end else begin
            // decode selects
            sram_sel   = (a <= 8'h1F) ? 1'b1 : 1'b0;
            uart_sel   = (a >= 8'h80 && a <= 8'h83) ? 1'b1 : 1'b0;
            cgra_sel   = ((a >= 8'h90 && a <= 8'h9B) || a == `ADDR_START) ? 1'b1 : 1'b0;
            sram_addr  = a[4:0];
            sram_wr_en = (a <= 8'h1F) ? mst_wr : 1'b0;
            sram_wdata = mst_wdata;
            // read mux
            if (a <= 8'h1F)
                mst_rdata = sram_rdata;
            else if (a >= 8'h80 && a <= 8'h83)
                mst_rdata = uart_rdata;
            else if ((a >= 8'h90 && a <= 8'h9B) || a == `ADDR_START)
                mst_rdata = cgra_rdata;
            else
                mst_rdata = 8'd0;
        end
    end

endmodule