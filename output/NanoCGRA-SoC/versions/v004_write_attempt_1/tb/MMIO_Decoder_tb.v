`timescale 1ns / 1ps

module MMIO_Decoder_tb;

    // Clock and Reset
    reg clk;
    reg rst_n;
    
    // DUT Signals
    reg [7:0] addr;
    reg [7:0] data_in;
    wire [7:0] data_out;
    wire write_en;
    wire read_en;
    wire write_ack;
    wire rdy;
    
    // Instantiate DUT
    MMIO_Decoder dut (
        .clk(clk),
        .rst_n(rst_n),
        .addr(addr),
        .data_in(data_in),
        .data_out(data_out),
        .write_en(write_en),
        .read_en(read_en),
        .write_ack(write_ack),
        .rdy(rdy)
    );

    // Clock Generation
    initial clk = 0;
    always #5 clk = ~clk;

    // Test Control
    integer cycles = 0;
    integer errors = 0;
    integer total_checks = 0;
    integer timeout_counter = 0;
    
    // Watchdog
    always @(posedge clk) begin
        cycles = cycles + 1;
        if (cycles > 2000000) begin
            $display("Result: FAILED (timeout)");
            $finish;
        end
    end

    // Test Sequences
    initial begin
        // Initialize
        clk = 0;
        rst_n = 0;
        addr = 8'd0;
        data_in = 8'd0;
        write_en = 0;
        read_en = 0;
        
        // Wait for reset
        @(posedge clk);
        @(posedge clk);
        
        rst_n = 1; // Release reset
        @(posedge clk);
        @(posedge clk);
        
        // --- TEST CASE 1: SRAM Write (Region 0x00-0x7F) ---
        addr = 8'd0x00;
        data_in = 8'd42;
        write_en = 1;
        @(posedge clk);
        @(posedge clk);
        // Expected: write_ack becomes 1 after write_valid clears
        if (write_ack === 1'b1) begin
            $display("CASE SRAM_WRITE: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> PASS", addr, data_in, write_ack);
            errors = errors + 0;
        end else begin
            $display("CASE SRAM_WRITE: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> FAIL", addr, data_in, write_ack);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        write_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 2: SRAM Read (Region 0x00-0x7F) ---
        addr = 8'd0x00;
        data_in = 8'd0;
        write_en = 0;
        @(posedge clk);
        @(posedge clk);
        // Expected: read_en becomes 1
        if (read_en === 1'b1) begin
            $display("CASE SRAM_READ: in=addr=0x%0h,exp_en=1,act_en=%0d -> PASS", addr, read_en);
            errors = errors + 0;
        end else begin
            $display("CASE SRAM_READ: in=addr=0x%0h,exp_en=1,act_en=%0d -> FAIL", addr, read_en);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        read_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 3: UART Write (Region 0x80-0x83) ---
        addr = 8'd0x80;
        data_in = 8'd'10101010;
        write_en = 1;
        @(posedge clk);
        @(posedge clk);
        if (write_ack === 1'b1) begin
            $display("CASE UART_WRITE: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> PASS", addr, data_in, write_ack);
            errors = errors + 0;
        end else begin
            $display("CASE UART_WRITE: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> FAIL", addr, data_in, write_ack);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        write_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 4: UART Read (Region 0x80-0x83) ---
        addr = 8'd0x80;
        data_in = 8'd0;
        write_en = 0;
        @(posedge clk);
        @(posedge clk);
        if (read_en === 1'b1) begin
            $display("CASE UART_READ: in=addr=0x%0h,exp_en=1,act_en=%0d -> PASS", addr, read_en);
            errors = errors + 0;
        end else begin
            $display("CASE UART_READ: in=addr=0x%0h,exp_en=1,act_en=%0d -> FAIL", addr, read_en);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        read_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 5: CGRA Config Write (Region 0x90-0x97) ---
        addr = 8'd0x90;
        data_in = 8'd'11110000;
        write_en = 1;
        @(posedge clk);
        @(posedge clk);
        if (write_ack === 1'b1) begin
            $display("CASE CGRA_WRITE: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> PASS", addr, data_in, write_ack);
            errors = errors + 0;
        end else begin
            $display("CASE CGRA_WRITE: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> FAIL", addr, data_in, write_ack);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        write_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 6: CGRA Config Read (Region 0x90-0x97) ---
        addr = 8'd0x90;
        data_in = 8'd0;
        write_en = 0;
        @(posedge clk);
        @(posedge clk);
        if (read_en === 1'b1) begin
            $display("CASE CGRA_READ: in=addr=0x%0h,exp_en=1,act_en=%0d -> PASS", addr, read_en);
            errors = errors + 0;
        end else begin
            $display("CASE CGRA_READ: in=addr=0x%0h,exp_en=1,act_en=%0d -> FAIL", addr, read_en);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        read_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 7: Boot ROM Write (Region 0xC0-0xFF) ---
        addr = 8'd0xC0;
        data_in = 8'd'11111111;
        write_en = 1;
        @(posedge clk);
        @(posedge clk);
        if (write_ack === 1'b1) begin
            $display("CASE BOOTROM_WRITE: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> PASS", addr, data_in, write_ack);
            errors = errors + 0;
        end else begin
            $display("CASE BOOTROM_WRITE: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> FAIL", addr, data_in, write_ack);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        write_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 8: Boot ROM Read (Region 0xC0-0xFF) ---
        addr = 8'd0xC0;
        data_in = 8'd0;
        write_en = 0;
        @(posedge clk);
        @(posedge clk);
        if (read_en === 1'b1) begin
            $display("CASE BOOTROM_READ: in=addr=0x%0h,exp_en=1,act_en=%0d -> PASS", addr, read_en);
            errors = errors + 0;
        end else begin
            $display("CASE BOOTROM_READ: in=addr=0x%0h,exp_en=1,act_en=%0d -> FAIL", addr, read_en);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        read_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 9: Unknown Address (Region > 0xFF or < 0x00 - effectively default) ---
        addr = 8'd0xFF;
        data_in = 8'd0;
        write_en = 0;
        @(posedge clk);
        @(posedge clk);
        // Expected: rdy=1, read_en=0, write_ack=0 (Default case)
        if (rdy === 1'b1 && read_en === 1'b0 && write_ack === 1'b0) begin
            $display("CASE UNKNOWN_ADDR: in=addr=0x%0h,exp_rdy=1,exp_read_en=0,exp_ack=0,act_rdy=%0d,act_read_en=%0d,act_ack=%0d -> PASS", addr, rdy, read_en, write_ack);
            errors = errors + 0;
        end else begin
            $display("CASE UNKNOWN_ADDR: in=addr=0x%0h,exp_rdy=1,exp_read_en=0,exp_ack=0,act_rdy=%0d,act_read_en=%0d,act_ack=%0d -> FAIL", addr, rdy, read_en, write_ack);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        write_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 10: Boundary Address 0x7F (SRAM High) ---
        addr = 8'd0x7F;
        data_in = 8'd0xDEADBEEF & 8'dFF;
        write_en = 1;
        @(posedge clk);
        @(posedge clk);
        if (write_ack === 1'b1) begin
            $display("CASE SRAM_HIGH: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> PASS", addr, data_in, write_ack);
            errors = errors + 0;
        end else begin
            $display("CASE SRAM_HIGH: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> FAIL", addr, data_in, write_ack);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        write_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 11: Boundary Address 0x83 (UART High) ---
        addr = 8'd0x83;
        data_in = 8'd0x55;
        write_en = 1;
        @(posedge clk);
        @(posedge clk);
        if (write_ack === 1'b1) begin
            $display("CASE UART_HIGH: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> PASS", addr, data_in, write_ack);
            errors = errors + 0;
        end else begin
            $display("CASE UART_HIGH: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> FAIL", addr, data_in, write_ack);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        write_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 12: Boundary Address 0x97 (CGRA High) ---
        addr = 8'd0x97;
        data_in = 8'd0xAA;
        write_en = 1;
        @(posedge clk);
        @(posedge clk);
        if (write_ack === 1'b1) begin
            $display("CASE CGRA_HIGH: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> PASS", addr, data_in, write_ack);
            errors = errors + 0;
        end else begin
            $display("CASE CGRA_HIGH: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> FAIL", addr, data_in, write_ack);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        write_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 13: Boundary Address 0xC0 (BootROM Low) ---
        addr = 8'd0xC0;
        data_in = 8'd0x00;
        write_en = 1;
        @(posedge clk);
        @(posedge clk);
        if (write_ack === 1'b1) begin
            $display("CASE BOOTROM_LOW: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> PASS", addr, data_in, write_ack);
            errors = errors + 0;
        end else begin
            $display("CASE BOOTROM_LOW: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> FAIL", addr, data_in, write_ack);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        write_en = 0;
        @(posedge clk);
        
        // --- TEST CASE 14: Boundary Address 0xFF (BootROM High) ---
        addr = 8'd0xFF;
        data_in = 8'd0xFF;
        write_en = 1;
        @(posedge clk);
        @(posedge clk);
        if (write_ack === 1'b1) begin
            $display("CASE BOOTROM_HIGH: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> PASS", addr, data_in, write_ack);
            errors = errors + 0;
        end else begin
            $display("CASE BOOTROM_HIGH: in=addr=0x%0h,data=0x%0h,exp_ack=1,act_ack=%0d -> FAIL", addr, data_in, write_ack);
            errors = errors + 1;
        end
        total_checks = total_checks + 1;
        write_en = 0;
        @(posedge clk);
        
        // --- SUMMARY ---
        $display("CYCLES: total=%0d", cycles);
        $display("SUMMARY: %0d checks, %0d failed", total_checks, errors);
        if (errors === 0) begin
            $display("Result: PASSED");
        end else begin
            $display("Result: FAILED");
        end
        $finish;
    end

endmodule