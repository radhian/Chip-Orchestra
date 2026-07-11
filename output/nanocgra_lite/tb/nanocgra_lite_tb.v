//============================================================================
// nanocgra_lite_tb.v  -  Top-level integration testbench (MMIO bus driven).
//   Loads operands into SRAM over the bus, configures a PE op, pulses START,
//   polls STATUS for done, then reads the result back from SRAM.
//   Exercises ADD and MUL end-to-end (SRAM -> CGRA -> SRAM).
//   expected=.. actual=.. labels + timeout watchdog.
//============================================================================
`timescale 1ns / 1ps
`include "params.vh"

module nanocgra_lite_tb;
    localparam DW = 8, AW = 8;

    reg              clk, rst_n;
    reg  [AW-1:0]    bus_addr;
    reg              bus_we, bus_re;
    reg  [DW-1:0]    bus_wdata;
    wire [DW-1:0]    bus_rdata;
    wire             uart_rx;
    wire             uart_tx;
    assign uart_rx = uart_tx;          // UART loopback: TX out -> RX in
    wire             busy;
    wire [DW-1:0]    cgra_status;

    integer errors, guard;

    NanoCGRA_Lite #(.DW(DW), .AW(AW), .UART_CLK_PER_BIT(8)) dut (
        .clk(clk), .rst_n(rst_n),
        .bus_addr(bus_addr), .bus_we(bus_we), .bus_re(bus_re),
        .bus_wdata(bus_wdata), .bus_rdata(bus_rdata),
        .uart_rx(uart_rx), .uart_tx(uart_tx),
        .busy(busy), .cgra_status(cgra_status));

    // 10 MHz clock
    initial clk = 1'b0;
    always #50 clk = ~clk;

    initial begin
        #500000;
        $display("Result: FAILED (timeout)");
        $finish;
    end

    task bus_write(input [AW-1:0] a, input [DW-1:0] d);
        begin
            @(negedge clk);
            bus_addr = a; bus_wdata = d; bus_we = 1'b1; bus_re = 1'b0;
            @(negedge clk);
            bus_we = 1'b0;
        end
    endtask

    // registered read (SRAM/UART latency = 1 clk)
    task bus_read(input [AW-1:0] a, output [DW-1:0] d);
        begin
            @(negedge clk);
            bus_addr = a; bus_re = 1'b1; bus_we = 1'b0;
            @(negedge clk);              // rdata now valid
            d = bus_rdata;
            bus_re = 1'b0;
        end
    endtask

    // run one CGRA op: cfg into PE0, operands into SRAM[0]/[1], read SRAM[0x10]
    task run_cgra(input [DW-1:0] cfg, input [DW-1:0] a, input [DW-1:0] b,
                  input [DW-1:0] exp, input [127:0] name);
        reg [DW-1:0] rd;
        begin
            bus_write(8'h00, a);          // SRAM[0]  = operand A
            bus_write(8'h01, b);          // SRAM[1]  = operand B
            bus_write(8'h90, cfg);        // PE(0,0) config
            bus_write(8'h94, 8'h00);      // opa_addr = 0
            bus_write(8'h95, 8'h01);      // opb_addr = 1
            bus_write(8'h96, 8'h10);      // res_addr = 0x10
            bus_write(8'hA0, 8'h01);      // START

            guard = 0;
            rd = 8'h00;
            while ((rd[1] == 1'b0) && (guard < 1000)) begin
                bus_read(8'hA1, rd);      // poll STATUS
                guard = guard + 1;
            end

            bus_read(8'h10, rd);          // read result from SRAM[0x10]
            if (rd === exp)
                $display("PASS  %0s  expected=%0d  actual=%0d", name, exp, rd);
            else begin
                $display("FAIL  %0s  expected=%0d  actual=%0d", name, exp, rd);
                errors = errors + 1;
            end
        end
    endtask

    reg [DW-1:0] tmp;
    reg [DW-1:0] ustat, urx;
    initial begin
        errors = 0;
        {bus_addr, bus_we, bus_re, bus_wdata} = 0;
        rst_n = 1'b0;
        repeat (3) @(negedge clk);
        rst_n = 1'b1;
        repeat (2) @(negedge clk);

        // Plain SRAM read/write sanity over the bus
        bus_write(8'h20, 8'd123);
        bus_read (8'h20, tmp);
        if (tmp === 8'd123)
            $display("PASS  SRAM_bus  expected=%0d  actual=%0d", 8'd123, tmp);
        else begin
            $display("FAIL  SRAM_bus  expected=%0d  actual=%0d", 8'd123, tmp);
            errors = errors + 1;
        end

        // CGRA ADD:  5 + 3 = 8   (op=ADD=0, bsel=N=0 -> cfg=0x00)
        run_cgra(8'h00, 8'd5, 8'd3, 8'd8, "CGRA_ADD");

        // CGRA MUL: 12 * 12 = 144 (op=MUL=5, bsel=N=0 -> cfg=0x05)
        run_cgra(8'h05, 8'd12, 8'd12, 8'd144, "CGRA_MUL");

        // CGRA XOR: 0xAA ^ 0xFF = 0x55 (op=XOR=4 -> cfg=0x04)
        run_cgra(8'h04, 8'hAA, 8'hFF, 8'h55, "CGRA_XOR");

        // End-to-end UART OUT: read computed result from SRAM[0x10], push it
        // out over UART TXDATA; loopback returns it into RX. Confirms the
        // result -> UART out chain (UART TX serialization + RX de-serialize).
        bus_read(8'h10, tmp);                 // last result committed by CGRA
        bus_write(8'h80, tmp);                // write result to UART TXDATA
        guard = 0; ustat = 8'h00;
        while ((ustat[1] == 1'b0) && (guard < 2000)) begin
            bus_read(8'h82, ustat);           // poll UART STATUS rx_valid
            guard = guard + 1;
        end
        bus_read(8'h81, urx);                 // read UART RXDATA
        if (urx === tmp)
            $display("PASS  UART_OUT_e2e  expected=%0d  actual=%0d", tmp, urx);
        else begin
            $display("FAIL  UART_OUT_e2e  expected=%0d  actual=%0d", tmp, urx);
            errors = errors + 1;
        end

        if (errors == 0) $display("Result: PASSED");
        else             $display("Result: FAILED (%0d mismatch)", errors);
        $finish;
    end
endmodule
