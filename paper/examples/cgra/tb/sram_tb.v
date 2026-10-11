//============================================================================
// sram_tb.v  -  Testbench for the 32B single-port SRAM.
//   * expected=.. actual=.. labels on every check
//   * timeout watchdog
//============================================================================
`timescale 1ns / 1ps
`include "params.vh"

module sram_tb;
    localparam DW = 8, AW = 5;

    reg              clk;
    reg              rst_n;
    reg  [AW-1:0]    addr;
    reg              we;
    reg  [DW-1:0]    din;
    wire [DW-1:0]    dout;

    integer errors;

    sram #(.DW(DW), .AW(AW), .DEPTH(32)) dut (
        .clk(clk), .rst_n(rst_n), .addr(addr), .we(we), .din(din), .dout(dout));

    // 10 MHz clock (100 ns period)
    initial clk = 1'b0;
    always #50 clk = ~clk;

    // Timeout watchdog
    initial begin
        #100000;
        $display("Result: FAILED (timeout)");
        $finish;
    end

    // single-cycle write helper
    task sram_write(input [AW-1:0] a, input [DW-1:0] d);
        begin
            @(negedge clk);
            addr = a; din = d; we = 1'b1;
            @(negedge clk);
            we = 1'b0;
        end
    endtask

    // registered read: present address, wait one clk, sample dout
    task sram_check(input [AW-1:0] a, input [DW-1:0] exp);
        begin
            @(negedge clk);
            addr = a; we = 1'b0;
            @(negedge clk);              // dout now reflects mem[a]
            if (dout === exp)
                $display("PASS  addr=%0d  expected=%0d  actual=%0d", a, exp, dout);
            else begin
                $display("FAIL  addr=%0d  expected=%0d  actual=%0d", a, exp, dout);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        errors = 0;
        rst_n  = 1'b0;
        addr   = {AW{1'b0}};
        din    = {DW{1'b0}};
        we     = 1'b0;
        repeat (2) @(negedge clk);
        rst_n = 1'b1;
        @(negedge clk);

        // Write / read-back several locations
        sram_write(5'd0,   8'd42);
        sram_write(5'd1,   8'd100);
        sram_write(5'd31,  8'd255);
        sram_write(5'd16,  8'd7);

        sram_check(5'd0,   8'd42);
        sram_check(5'd1,   8'd100);
        sram_check(5'd31,  8'd255);
        sram_check(5'd16,  8'd7);

        // Overwrite test
        sram_write(5'd0, 8'd200);
        sram_check(5'd0, 8'd200);

        if (errors == 0)
            $display("Result: PASSED");
        else
            $display("Result: FAILED (%0d mismatch)", errors);
        $finish;
    end
endmodule
