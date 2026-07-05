`timescale 1ns / 1ps

module Boot_ROM_tb;

    // Inputs
    reg                    clk;
    reg                    rst_n;
    reg [7:0]              addr;
    
    // Outputs
    wire [7:0]             data_out;
    wire                   rdy;

    // Instantiate DUT
    Boot_ROM uut (
        .clk           (clk),
        .rst_n         (rst_n),
        .addr          (addr),
        .data_out      (data_out),
        .rdy           (rdy)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk;  // 10 MHz clock (100 ns period)
    end

    // Test sequence
    initial begin
        // Initialize
        rst_n = 0;
        addr  = 0;
        #100;  // Wait for reset
        
        rst_n = 1;
        #100;  // Wait for stable
        
        $display("=== Boot_ROM Testbench ===");
        $display("Testing ROM read at various addresses...");
        
        // Test read at various addresses
        for (integer i = 0; i < 64; i = i + 1) begin
            addr = i[7:0];
            @(posedge clk);
            @(posedge clk);  // Wait for data to stabilize
            $display("Addr = %0h, Data = %0h, rdy = %b", addr, data_out, rdy);
        end
        
        // Verify specific addresses
        $display("\n=== Verification ===");
        addr = 0;
        @(posedge clk);
        @(posedge clk);
        if (data_out == 8'h00) $display("PASS: mem[0] = NOP");
        else $display("FAIL: mem[0] = %0h (expected NOP)", data_out);
        
        addr = 16;
        @(posedge clk);
        @(posedge clk);
        if (data_out == 8'h10) $display("PASS: mem[16] = LOAD");
        else $display("FAIL: mem[16] = %0h (expected LOAD)", data_out);
        
        addr = 32;
        @(posedge clk);
        @(posedge clk);
        if (data_out == 8'h20) $display("PASS: mem[32] = UART init");
        else $display("FAIL: mem[32] = %0h (expected UART init)", data_out);
        
        addr = 63;
        @(posedge clk);
        @(posedge clk);
        if (data_out == 8'h3F) $display("PASS: mem[63] = NOP");
        else $display("FAIL: mem[63] = %0h (expected NOP)", data_out);
        
        // Test out-of-bounds address
        addr = 127;
        @(posedge clk);
        @(posedge clk);
        if (data_out == 8'd0 && rdy == 0) $display("PASS: Out-of-bounds returns 0");
        else $display("FAIL: Out-of-bounds returned %0h, rdy = %b", data_out, rdy);
        
        $display("\n=== Test Complete ===");
        $finish;
    end

endmodule
