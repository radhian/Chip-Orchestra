// tb/baud_gen_tb.v — unit testbench for baud_gen.
// Vectors from golden/vectors/baud_gen.json (1309 vectors).
// Uses $readmemh files for compact data storage.
`include "params.vh"

`timescale 1ns/1ps

module baud_gen_tb;

    reg clk;
    reg rst_n;
    wire baud_tick;

    integer i;
    integer errors;

    // DUT
    baud_gen dut (
        .clk(clk),
        .rst_n(rst_n),
        .baud_tick(baud_tick)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    // Vector data loaded from mem files
    reg [0:0] v_rst [0:1308];
    reg [0:0] v_exp [0:1308];

    initial begin
        $readmemh("tb/vecs/baud_rst.mem", v_rst);
        $readmemh("tb/vecs/baud_exp.mem", v_exp);

        errors = 0;
        rst_n = 0;
        @(negedge clk);
        @(negedge clk);

        for (i = 0; i < 1309; i = i + 1) begin
            rst_n = v_rst[i];
            @(posedge clk);
            #1;
            if (baud_tick !== v_exp[i]) begin
                $display("vec %0d: in(rst_n=%b) expected=%b actual=%b", i, v_rst[i], v_exp[i], baud_tick);
                errors = errors + 1;
                if (errors > 10) begin
                    $display("Too many errors, stopping");
                    $fatal(1);
                end
            end else if (v_exp[i] == 1'b1) begin
                $display("vec %0d: in(rst_n=%b) expected=%b actual=%b OK (TICK)", i, v_rst[i], v_exp[i], baud_tick);
            end
            @(negedge clk);
        end

        if (errors == 0)
            $display("baud_gen TEST PASSED");
        else begin
            $display("baud_gen TEST FAILED: %0d errors", errors);
            $fatal(1);
        end
        $finish;
    end

endmodule