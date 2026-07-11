//============================================================================
// uart_tb.v  -  UART loopback testbench (uart_tx wired back to uart_rx).
//   Transmits a byte via the memory-mapped TXDATA register, then checks the
//   received byte in RXDATA. expected=.. actual=.. labels + timeout watchdog.
//============================================================================
`timescale 1ns / 1ps
`include "params.vh"

module uart_tb;
    localparam DW = 8;
    localparam CPB = 8;              // small clocks-per-bit for fast sim

    reg           clk, rst_n;
    reg           we, re;
    reg  [1:0]    reg_sel;
    reg  [DW-1:0] wdata;
    wire [DW-1:0] rdata;
    wire          serial;            // loopback wire

    integer errors, guard;

    uart #(.DW(DW), .CLK_PER_BIT(CPB)) dut (
        .clk(clk), .rst_n(rst_n),
        .we(we), .re(re), .reg_sel(reg_sel), .wdata(wdata), .rdata(rdata),
        .uart_rx(serial), .uart_tx(serial));   // loopback

    initial clk = 1'b0;
    always #50 clk = ~clk;

    initial begin
        #500000;
        $display("Result: FAILED (timeout)");
        $finish;
    end

    task bus_write(input [1:0] a, input [DW-1:0] d);
        begin
            @(negedge clk);
            reg_sel = a; wdata = d; we = 1'b1;
            @(negedge clk);
            we = 1'b0;
        end
    endtask

    task bus_read(input [1:0] a, output [DW-1:0] d);
        begin
            @(negedge clk);
            reg_sel = a; re = 1'b1;
            #1 d = rdata;
            @(negedge clk);
            re = 1'b0;
        end
    endtask

    reg [DW-1:0] rd;
    initial begin
        errors = 0;
        rst_n = 1'b0;
        {we, re, reg_sel, wdata} = 0;
        repeat (3) @(negedge clk);
        rst_n = 1'b1;
        repeat (2) @(negedge clk);

        // Transmit 0xA5 over the loopback line
        bus_write(2'd0, 8'hA5);          // write TXDATA

        // Poll STATUS until rx_valid (bit1) set, bounded by guard
        guard = 0;
        rd = 8'h00;
        while ((rd[1] == 1'b0) && (guard < 2000)) begin
            bus_read(2'd2, rd);          // read STATUS
            guard = guard + 1;
        end

        if (rd[1] == 1'b1)
            $display("PASS  rx_valid asserted  expected=1  actual=%0d", rd[1]);
        else begin
            $display("FAIL  rx_valid never asserted  expected=1  actual=%0d", rd[1]);
            errors = errors + 1;
        end

        // Read the received byte
        bus_read(2'd1, rd);              // read RXDATA
        if (rd === 8'hA5)
            $display("PASS  RXDATA  expected=%0d  actual=%0d", 8'hA5, rd);
        else begin
            $display("FAIL  RXDATA  expected=%0d  actual=%0d", 8'hA5, rd);
            errors = errors + 1;
        end

        if (errors == 0) $display("Result: PASSED");
        else             $display("Result: FAILED (%0d mismatch)", errors);
        $finish;
    end
endmodule
