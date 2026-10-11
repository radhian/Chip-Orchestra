//============================================================================
// nanocgra_lite_tb.v  -  Top-level integration testbench (UART-ONLY, 4-pin).
//   *** OPT VARIANT ***
//   The DUT now exposes only clk / rst_n / uart_rx / uart_tx. The host drives
//   3-byte serial command packets on uart_rx and reads reply bytes on uart_tx.
//
//   Packet protocol (LSB-first bytes): [CMD][ADDR][DATA]
//     CMD=0x01 WRITE addr<=data ; CMD=0x02 READ addr (reply byte via TX) ;
//     CMD=0x03 RUN (write START).
//
//   Test flow (per op): write operands into SRAM, write PE config + operand
//   pointers, RUN, then READ result back over UART and check it.
//   Covers ADD, MUL, XOR end-to-end (SRAM -> CGRA -> SRAM -> UART TX).
//============================================================================
`timescale 1ns / 1ps
`include "params.vh"

module nanocgra_lite_tb;
    localparam DW = 8, AW = 8;
    localparam CPB = 8;                 // UART CLK_PER_BIT used in DUT + TB
    localparam integer BITT = CPB * 100;// one bit time in ns (100 ns clk)

    reg  clk, rst_n;
    reg  uart_rx;
    wire uart_tx;

    integer errors;

    NanoCGRA_Lite #(.DW(DW), .AW(AW), .UART_CLK_PER_BIT(CPB)) dut (
        .clk(clk), .rst_n(rst_n),
        .uart_rx(uart_rx), .uart_tx(uart_tx));

    // 10 MHz clock
    initial clk = 1'b0;
    always #50 clk = ~clk;

    // global watchdog
    initial begin
        #20000000;
        $display("Result: FAILED (timeout)");
        $finish;
    end

    // ---- send one UART byte on uart_rx (8N1, LSB first) --------------
    task uart_send_byte(input [7:0] b);
        integer i;
        begin
            uart_rx = 1'b0;             // start bit
            #(BITT);
            for (i = 0; i < 8; i = i + 1) begin
                uart_rx = b[i];
                #(BITT);
            end
            uart_rx = 1'b1;             // stop bit
            #(BITT);
            #(BITT);                    // idle gap between bytes
        end
    endtask

    // ---- send a 3-byte command packet --------------------------------
    task send_pkt(input [7:0] cmd, input [7:0] addr, input [7:0] data);
        begin
            uart_send_byte(cmd);
            uart_send_byte(addr);
            uart_send_byte(data);
        end
    endtask

    // ---- receive one UART byte from uart_tx (blocking) ---------------
    task uart_recv_byte(output [7:0] b);
        integer i;
        begin
            // wait for start bit (falling edge on idle-high line)
            @(negedge uart_tx);
            #(BITT + BITT/2);           // skip start bit, center of bit0
            for (i = 0; i < 8; i = i + 1) begin
                b[i] = uart_tx;
                #(BITT);
            end
            // now in stop bit
            #(BITT/2);
        end
    endtask

    // ---- convenience: program + run one CGRA op, read + check --------
    task run_cgra(input [7:0] cfg, input [7:0] a, input [7:0] b,
                  input [7:0] exp, input [127:0] name);
        reg [7:0] rd;
        begin
            send_pkt(8'h01, 8'h00, a);      // SRAM[0]  = operand A
            send_pkt(8'h01, 8'h01, b);      // SRAM[1]  = operand B
            send_pkt(8'h01, 8'h90, cfg);    // PE(0,0) config
            send_pkt(8'h01, 8'h99, 8'h00);  // opa_addr = 0
            send_pkt(8'h01, 8'h9A, 8'h01);  // opb_addr = 1
            send_pkt(8'h01, 8'h9B, 8'h10);  // res_addr = 0x10
            send_pkt(8'h03, 8'h00, 8'h01);  // RUN
            // give the CGRA time to finish before requesting the result
            repeat (200) @(posedge clk);
            send_pkt(8'h02, 8'h10, 8'h00);  // READ SRAM[0x10] -> reply via TX
            uart_recv_byte(rd);
            if (rd === exp)
                $display("PASS  %0s  expected=%0d  actual=%0d", name, exp, rd);
            else begin
                $display("FAIL  %0s  expected=%0d  actual=%0d", name, exp, rd);
                errors = errors + 1;
            end
        end
    endtask

    reg [7:0] rd;
    initial begin
        errors  = 0;
        uart_rx = 1'b1;                 // idle high
        rst_n   = 1'b0;
        repeat (5) @(negedge clk);
        rst_n   = 1'b1;
        repeat (5) @(negedge clk);

        // ---- Plain SRAM write/read-back over UART (addr 0x08) --------
        send_pkt(8'h01, 8'h08, 8'd123); // WRITE SRAM[8] = 123
        send_pkt(8'h02, 8'h08, 8'h00);  // READ  SRAM[8]
        uart_recv_byte(rd);
        if (rd === 8'd123)
            $display("PASS  SRAM_uart  expected=%0d  actual=%0d", 8'd123, rd);
        else begin
            $display("FAIL  SRAM_uart  expected=%0d  actual=%0d", 8'd123, rd);
            errors = errors + 1;
        end

        // CGRA ADD:  5 + 3 = 8    (op=ADD=0 -> cfg=0x00)
        run_cgra(8'h00, 8'd5,  8'd3,  8'd8,   "CGRA_ADD");
        // CGRA MUL: 12 * 12 = 144 (op=MUL=5 -> cfg=0x05)
        run_cgra(8'h05, 8'd12, 8'd12, 8'd144, "CGRA_MUL");
        // CGRA XOR: 0xAA ^ 0xFF = 0x55 (op=XOR=4 -> cfg=0x04)
        run_cgra(8'h04, 8'hAA, 8'hFF, 8'h55,  "CGRA_XOR");

        if (errors == 0) $display("Result: PASSED");
        else             $display("Result: FAILED (%0d mismatch)", errors);
        $finish;
    end
endmodule
