module SRAM_128_tb;

    // Clock and Reset
    reg clk;
    reg rst_n;
    
    // DUT Instantiation
    // No parameters to override for this specific SRAM block
    SRAM_128 dut (
        .clk      (clk),
        .rst_n    (rst_n),
        .addr     (addr),
        .data_in  (data_in),
        .data_out (data_out),
        .write_en (write_en),
        .read_en  (read_en),
        .rdy      (rdy)
    );

    // Test Stimulus and Control
    reg [7:0] addr;
    reg [7:0] data_in;
    reg write_en;
    reg read_en;
    wire [7:0] data_out;
    wire rdy;

    integer cycles;
    integer errors;
    integer i;
    integer exp_data;
    integer act_data;
    integer timeout_count;
    
    // Initialize counters
    initial begin
        cycles = 0;
        errors = 0;
        timeout_count = 0;
        addr = 8'd0;
        data_in = 8'd0;
        write_en = 1'b0;
        read_en = 1'b0;
        clk = 1'b0;
        rst_n = 1'b0;
    end

    // Clock Generation
    always #5 clk = ~clk;

    // Test Sequence
    initial begin
        // 1. Apply Reset
        rst_n = 1'b0;
        #100; // Wait for reset to settle
        rst_n = 1'b1;
        #100; // Wait for initialization
        
        // 2. Write Test Cases
        // Case 1: Write to address 0
        addr = 8'd0;
        data_in = 8'd10;
        write_en = 1'b1;
        read_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // Case 2: Write to address 127 (Boundary)
        addr = 8'd127;
        data_in = 8'd255;
        write_en = 1'b1;
        read_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // Case 3: Write to middle address
        addr = 8'd64;
        data_in = 8'd42;
        write_en = 1'b1;
        read_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // Case 4: Write with 0 data
        addr = 8'd10;
        data_in = 8'd0;
        write_en = 1'b1;
        read_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // Case 5: Write with Max data
        addr = 8'd20;
        data_in = 8'd255;
        write_en = 1'b1;
        read_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // 3. Read Test Cases
        // Case 6: Read back address 0
        write_en = 1'b0;
        read_en = 1'b1;
        @(posedge clk);
        wait (rdy);
        
        // Case 7: Read back address 127
        addr = 8'd127;
        read_en = 1'b1;
        write_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // Case 8: Read back address 64
        addr = 8'd64;
        read_en = 1'b1;
        write_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // Case 9: Read back address 10 (was 0)
        addr = 8'd10;
        read_en = 1'b1;
        write_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // Case 10: Read back address 20 (was 255)
        addr = 8'd20;
        read_en = 1'b1;
        write_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // Case 11: Read without write (should return 0)
        addr = 8'd50;
        read_en = 1'b1;
        write_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // Case 12: Read immediately after write (same cycle)
        addr = 8'd30;
        data_in = 8'd99;
        write_en = 1'b1;
        read_en = 1'b1;
        @(posedge clk);
        wait (rdy);
        
        // Case 13: Rapid toggle (Write then Read same addr)
        addr = 8'd40;
        data_in = 8'd123;
        write_en = 1'b1;
        read_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        read_en = 1'b1;
        write_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // Case 14: Read after reset (should be 0)
        // Note: Reset logic clears mem, so reading any addr should be 0
        addr = 8'd99;
        read_en = 1'b1;
        write_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // Case 15: Write then Read different address
        addr = 8'd11;
        data_in = 8'd77;
        write_en = 1'b1;
        read_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        addr = 8'd12;
        read_en = 1'b1;
        write_en = 1'b0;
        @(posedge clk);
        wait (rdy);
        
        // 4. Timeout Watchdog
        timeout_count = 0;
        while (timeout_count < 2000000) begin
            @(posedge clk);
            timeout_count = timeout_count + 1;
        end
        
        // 5. Print Results
        $display("CYCLES: total=%0d", cycles);
        
        // Print individual case results (re-evaluating logic for display)
        // Case 1
        $display("CASE write_0: in=addr=%0d,data=%0d expected=%0d actual=%0d -> %s", 
                  0, 10, 10, data_out, (data_out==10) ? "PASS" : "FAIL");
        errors = errors + (data_out==10 ? 0 : 1);
        
        // Case 2
        $display("CASE write_127: in=addr=%0d,data=%0d expected=%0d actual=%0d -> %s", 
                  127, 255, 255, data_out, (data_out==255) ? "PASS" : "FAIL");
        errors = errors + (data_out==255 ? 0 : 1);
        
        // Case 3
        $display("CASE write_64: in=addr=%0d,data=%0d expected=%0d actual=%0d -> %s", 
                  64, 42, 42, data_out, (data_out==42) ? "PASS" : "FAIL");
        errors = errors + (data_out==42 ? 0 : 1);
        
        // Case 4
        $display("CASE write_10_zero: in=addr=%0d,data=%0d expected=%0d actual=%0d -> %s", 
                  10, 0, 0, data_out, (data_out==0) ? "PASS" : "FAIL");
        errors = errors + (data_out==0 ? 0 : 1);
        
        // Case 5
        $display("CASE write_20_max: in=addr=%0d,data=%0d expected=%0d actual=%0d -> %s", 
                  20, 255, 255, data_out, (data_out==255) ? "PASS" : "FAIL");
        errors = errors + (data_out==255 ? 0 : 1);
        
        // Case 6
        $display("CASE read_0: in=addr=%0d expected=%0d actual=%0d -> %s", 
                  0, 10, data_out, (data_out==10) ? "PASS" : "FAIL");
        errors = errors + (data_out==10 ? 0 : 1);
        
        // Case 7
        $display("CASE read_127: in=addr=%0d expected=%0d actual=%0d -> %s", 
                  127, 255, data_out, (data_out==255) ? "PASS" : "FAIL");
        errors = errors + (data_out==255 ? 0 : 1);
        
        // Case 8
        $display("CASE read_64: in=addr=%0d expected=%0d actual=%0d -> %s", 
                  64, 42, data_out, (data_out==42) ? "PASS" : "FAIL");
        errors = errors + (data_out==42 ? 0 : 1);
        
        // Case 9
        $display("CASE read_10_zero: in=addr=%0d expected=%0d actual=%0d -> %s", 
                  10, 0, data_out, (data_out==0) ? "PASS" : "FAIL");
        errors = errors + (data_out==0 ? 0 : 1);
        
        // Case 10
        $display("CASE read_20_max: in=addr=%0d expected=%0d actual=%0d -> %s", 
                  20, 255, data_out, (data_out==255) ? "PASS" : "FAIL");
        errors = errors + (data_out==255 ? 0 : 1);
        
        // Case 11
        $display("CASE read_50_empty: in=addr=%0d expected=%0d actual=%0d -> %s", 
                  50, 0, data_out, (data_out==0) ? "PASS" : "FAIL");
        errors = errors + (data_out==0 ? 0 : 1);
        
        // Case 12
        $display("CASE write_read_same: in=addr=%0d,data=%0d expected=%0d actual=%0d -> %s", 
                  30, 99, 99, data_out, (data_out==99) ? "PASS" : "FAIL");
        errors = errors + (data_out==99 ? 0 : 1);
        
        // Case 13
        $display("CASE write_read_toggle: in=addr=%0d,data=%0d expected=%0d actual=%0d -> %s", 
                  40, 123, 123, data_out, (data_out==123) ? "PASS" : "FAIL");
        errors = errors + (data_out==123 ? 0 : 1);
        
        // Case 14
        $display("CASE read_after_reset: in=addr=%0d expected=%0d actual=%0d -> %s", 
                  99, 0, data_out, (data_out==0) ? "PASS" : "FAIL");
        errors = errors + (data_out==0 ? 0 : 1);
        
        // Case 15
        $display("CASE read_diff_addr: in=addr=%0d expected=%0d actual=%0d -> %s", 
                  12, 0, data_out, (data_out==0) ? "PASS" : "FAIL");
        errors = errors + (data_out==0 ? 0 : 1);
        
        // Summary
        $display("SUMMARY: %0d checks, %0d failed", 15, errors);
        if (errors == 0) begin
            $display("Result: PASSED");
        end else begin
            $display("Result: FAILED");
        end
        
        $finish;
    end

endmodule