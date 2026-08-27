// tb/reset_sync_tb.v — unit testbench for reset_sync.
// Vectors from golden/vectors/reset_sync.json (14 vectors).
`include "params.vh"

`timescale 1ns/1ps

module reset_sync_tb;

    reg clk;
    reg rst_async_n;
    wire rst_n;

    integer i;
    integer errors;

    // Expected rst_n values from golden vectors
    reg [0:13] exp_rst_n = 14'b011111000001111;

    // DUT
    reset_sync dut (
        .clk(clk),
        .rst_async_n(rst_async_n),
        .rst_n(rst_n)
    );

    // Clock
    initial clk = 0;
    always #5 clk = ~clk;

    // Stimulus from golden vectors:
    // vec 0-4:  rst_async_n=1
    // vec 5-9:  rst_async_n=0
    // vec 10-13: rst_async_n=1
    reg [0:13] stim_rst_async_n = 14'b111110000011111;

    initial begin
        errors = 0;
        rst_async_n = 0;

        // Apply reset for 2 cycles to initialize
        @(negedge clk);
        rst_async_n = 0;
        @(negedge clk);
        @(negedge clk);

        // Now drive the 14 vectors
        for (i = 0; i < 14; i = i + 1) begin
            rst_async_n = stim_rst_async_n[i];
            @(posedge clk);
            #1;
            if (rst_n !== exp_rst_n[i]) begin
                $display("vec %0d: in(rst_async_n=%b) expected=%b actual=%b", i, stim_rst_async_n[i], exp_rst_n[i], rst_n);
                errors = errors + 1;
            end else begin
                $display("vec %0d: in(rst_async_n=%b) expected=%b actual=%b OK", i, stim_rst_async_n[i], exp_rst_n[i], rst_n);
            end
        end

        if (errors == 0)
            $display("reset_sync TEST PASSED");
        else begin
            $display("reset_sync TEST FAILED: %0d errors", errors);
            $fatal(1);
        end
        $finish;
    end

endmodule