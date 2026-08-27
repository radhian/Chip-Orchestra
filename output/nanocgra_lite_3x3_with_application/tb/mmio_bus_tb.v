// tb/mmio_bus_tb.v — unit testbench for mmio_bus.
// Vectors from golden/vectors/mmio_bus.json (6 vectors).
// Combinational module.
`include "params.vh"

`timescale 1ns/1ps

module mmio_bus_tb;

    reg clk;
    reg rst_n;
    reg [7:0] mst_addr;
    reg mst_wr;
    reg mst_rd;
    reg [7:0] mst_wdata;
    reg [7:0] sram_rdata;
    reg [7:0] uart_rdata;
    reg [7:0] cgra_rdata;
    wire [7:0] mst_rdata;
    wire sram_sel;
    wire uart_sel;
    wire cgra_sel;
    wire [4:0] sram_addr;
    wire sram_wr_en;
    wire [7:0] sram_wdata;

    integer i;
    integer errors;

    // DUT
    mmio_bus dut (
        .clk(clk),
        .rst_n(rst_n),
        .mst_addr(mst_addr),
        .mst_wr(mst_wr),
        .mst_rd(mst_rd),
        .mst_wdata(mst_wdata),
        .mst_rdata(mst_rdata),
        .sram_sel(sram_sel),
        .uart_sel(uart_sel),
        .cgra_sel(cgra_sel),
        .sram_addr(sram_addr),
        .sram_wr_en(sram_wr_en),
        .sram_wdata(sram_wdata),
        .sram_rdata(sram_rdata),
        .uart_rdata(uart_rdata),
        .cgra_rdata(cgra_rdata)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    // Vectors
    reg [0:5] v_rst_n = 6'b111110;
    reg [7:0] v_addr [0:5];
    reg [0:5] v_wr   = 6'b000110;
    reg [0:5] v_rd   = 6'b111000;
    reg [7:0] v_wdata [0:5];
    reg [7:0] v_sram_rd [0:5];
    reg [7:0] v_uart_rd [0:5];
    reg [7:0] v_cgra_rd [0:5];
    reg [7:0] v_exp_rdata [0:5];
    reg [0:5] v_exp_sram_sel = 6'b100010;
    reg [0:5] v_exp_uart_sel = 6'b010000;
    reg [0:5] v_exp_cgra_sel = 6'b001100;
    reg [4:0] v_exp_sram_addr [0:5];
    reg [0:5] v_exp_sram_wr   = 6'b000010;
    reg [7:0] v_exp_sram_wdata [0:5];

    initial begin
        // vec 0: addr=16, rd=1, sram_rdata=66 -> rdata=66, sram_sel=1, sram_addr=16
        v_addr[0]=8'd16; v_wdata[0]=8'd0; v_sram_rd[0]=8'd66; v_uart_rd[0]=8'd0; v_cgra_rd[0]=8'd0;
        v_exp_rdata[0]=8'd66; v_exp_sram_addr[0]=5'd16; v_exp_sram_wdata[0]=8'd0;
        // vec 1: addr=128, rd=1, uart_rdata=85 -> rdata=85, uart_sel=1
        v_addr[1]=8'd128; v_wdata[1]=8'd0; v_sram_rd[1]=8'd0; v_uart_rd[1]=8'd85; v_cgra_rd[1]=8'd0;
        v_exp_rdata[1]=8'd85; v_exp_sram_addr[1]=5'd0; v_exp_sram_wdata[1]=8'd0;
        // vec 2: addr=144, rd=1, cgra_rdata=119 -> rdata=119, cgra_sel=1, sram_addr=16
        v_addr[2]=8'd144; v_wdata[2]=8'd0; v_sram_rd[2]=8'd0; v_uart_rd[2]=8'd0; v_cgra_rd[2]=8'd119;
        v_exp_rdata[2]=8'd119; v_exp_sram_addr[2]=5'd16; v_exp_sram_wdata[2]=8'd0;
        // vec 3: addr=160, wr=1, wdata=1 -> cgra_sel=1, sram_wdata=1
        v_addr[3]=8'd160; v_wdata[3]=8'd1; v_sram_rd[3]=8'd0; v_uart_rd[3]=8'd0; v_cgra_rd[3]=8'd0;
        v_exp_rdata[3]=8'd0; v_exp_sram_addr[3]=5'd0; v_exp_sram_wdata[3]=8'd1;
        // vec 4: addr=5, wr=1, wdata=171 -> sram_sel=1, sram_addr=5, sram_wr=1, sram_wdata=171
        v_addr[4]=8'd5; v_wdata[4]=8'd171; v_sram_rd[4]=8'd0; v_uart_rd[4]=8'd0; v_cgra_rd[4]=8'd0;
        v_exp_rdata[4]=8'd0; v_exp_sram_addr[4]=5'd5; v_exp_sram_wdata[4]=8'd171;
        // vec 5: rst_n=0 -> all zeros
        v_addr[5]=8'd0; v_wdata[5]=8'd0; v_sram_rd[5]=8'd0; v_uart_rd[5]=8'd0; v_cgra_rd[5]=8'd0;
        v_exp_rdata[5]=8'd0; v_exp_sram_addr[5]=5'd0; v_exp_sram_wdata[5]=8'd0;

        errors = 0;
        rst_n = 1;
        @(negedge clk);

        for (i = 0; i < 6; i = i + 1) begin
            rst_n = v_rst_n[i];
            mst_addr = v_addr[i];
            mst_wr = v_wr[i];
            mst_rd = v_rd[i];
            mst_wdata = v_wdata[i];
            sram_rdata = v_sram_rd[i];
            uart_rdata = v_uart_rd[i];
            cgra_rdata = v_cgra_rd[i];
            #1;
            if (mst_rdata !== v_exp_rdata[i] ||
                sram_sel !== v_exp_sram_sel[i] ||
                uart_sel !== v_exp_uart_sel[i] ||
                cgra_sel !== v_exp_cgra_sel[i] ||
                sram_addr !== v_exp_sram_addr[i] ||
                sram_wr_en !== v_exp_sram_wr[i] ||
                sram_wdata !== v_exp_sram_wdata[i]) begin
                $display("vec %0d: in(addr=%0d,wr=%b,rd=%b,wdata=%0d,rst_n=%b)", i, v_addr[i], v_wr[i], v_rd[i], v_wdata[i], v_rst_n[i]);
                $display("  expected: rdata=%0d sram_sel=%b uart_sel=%b cgra_sel=%b sram_addr=%0d sram_wr=%b sram_wdata=%0d",
                    v_exp_rdata[i], v_exp_sram_sel[i], v_exp_uart_sel[i], v_exp_cgra_sel[i], v_exp_sram_addr[i], v_exp_sram_wr[i], v_exp_sram_wdata[i]);
                $display("  actual:   rdata=%0d sram_sel=%b uart_sel=%b cgra_sel=%b sram_addr=%0d sram_wr=%b sram_wdata=%0d",
                    mst_rdata, sram_sel, uart_sel, cgra_sel, sram_addr, sram_wr_en, sram_wdata);
                errors = errors + 1;
            end else begin
                $display("vec %0d: in(addr=%0d,wr=%b,rd=%b,wdata=%0d,rst_n=%b) expected(rdata=%0d) actual(rdata=%0d) OK",
                    i, v_addr[i], v_wr[i], v_rd[i], v_wdata[i], v_rst_n[i], v_exp_rdata[i], mst_rdata);
            end
            @(negedge clk);
        end

        if (errors == 0)
            $display("mmio_bus TEST PASSED");
        else begin
            $display("mmio_bus TEST FAILED: %0d errors", errors);
            $fatal(1);
        end
        $finish;
    end

endmodule