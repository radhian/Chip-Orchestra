// tb/sram_32b_tb.v — unit testbench for sram_32b.
// Vectors from golden/vectors/sram_32b.json (65 vectors).
`include "params.vh"

`timescale 1ns/1ps

module sram_32b_tb;

    reg clk;
    reg rst_n;
    reg [4:0] addr;
    reg wr_en;
    reg [7:0] data_in;
    wire [7:0] data_out;

    integer i;
    integer errors;

    // DUT
    sram_32b dut (
        .clk(clk),
        .rst_n(rst_n),
        .addr(addr),
        .wr_en(wr_en),
        .data_in(data_in),
        .data_out(data_out)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    // Vectors: 65 entries
    // vecs 0-31: write 0,2,4,...,62 to addrs 0..31
    // vecs 32-63: read back addrs 0..31 (expect 0,2,4,...,62)
    // vec 64: rst_n=0 -> data_out=0
    reg [4:0] v_addr [0:64];
    reg [0:64] v_wr_en;
    reg [0:64] v_rst_n;
    reg [7:0] v_data_in [0:64];
    reg [7:0] v_exp [0:64];

    integer j;
    initial begin
        // vecs 0-31: write even values
        for (j = 0; j < 32; j = j + 1) begin
            v_addr[j] = j[4:0];
            v_wr_en[j] = 1'b1;
            v_rst_n[j] = 1'b1;
            v_data_in[j] = j * 2;
            v_exp[j] = j * 2;
        end
        // vecs 32-63: read back
        for (j = 0; j < 32; j = j + 1) begin
            v_addr[32+j] = j[4:0];
            v_wr_en[32+j] = 1'b0;
            v_rst_n[32+j] = 1'b1;
            v_data_in[32+j] = 8'd0;
            v_exp[32+j] = j * 2;
        end
        // vec 64: reset
        v_addr[64] = 5'd0;
        v_wr_en[64] = 1'b0;
        v_rst_n[64] = 1'b0;
        v_data_in[64] = 8'd0;
        v_exp[64] = 8'd0;

        errors = 0;
        rst_n = 0;
        addr = 0; wr_en = 0; data_in = 0;
        @(negedge clk);
        @(negedge clk);

        for (i = 0; i < 65; i = i + 1) begin
            rst_n = v_rst_n[i];
            addr = v_addr[i];
            wr_en = v_wr_en[i];
            data_in = v_data_in[i];
            @(posedge clk);
            #1;
            if (data_out !== v_exp[i]) begin
                $display("vec %0d: in(addr=%0d,wr_en=%b,data_in=%0d,rst_n=%b) expected=%0d actual=%0d",
                    i, v_addr[i], v_wr_en[i], v_data_in[i], v_rst_n[i], v_exp[i], data_out);
                errors = errors + 1;
            end else begin
                $display("vec %0d: in(addr=%0d,wr_en=%b,data_in=%0d,rst_n=%b) expected=%0d actual=%0d OK",
                    i, v_addr[i], v_wr_en[i], v_data_in[i], v_rst_n[i], v_exp[i], data_out);
            end
            @(negedge clk);
        end

        if (errors == 0)
            $display("sram_32b TEST PASSED");
        else begin
            $display("sram_32b TEST FAILED: %0d errors", errors);
            $fatal(1);
        end
        $finish;
    end

endmodule