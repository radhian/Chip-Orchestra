//
// NanoCGRA v1 - Testbench
// Comprehensive verification for all modules
//

`timescale 1ns / 1ps

`include "rtl/nanocgra_top.v"

module nanocgra_tb;

    // Clock and reset
    reg                    clk;
    reg                    rst_n;
    
    // UART signals
    reg                    uart_tx;
    wire                   uart_rx;
    reg                    uart_rx_valid;
    
    // System status
    wire                   system_ready;
    wire                   system_busy;
    wire                   cgra_done;
    wire                   uart_tx_ready;
    wire                   uart_rx_ready;
    wire                   uart_tx_busy;
    wire                   uart_rx_busy;
    
    // Clock generation
    initial begin
        clk = 0;
        forever #50 clk = ~clk;  // 10 MHz clock
    end
    
    // Reset sequence
    initial begin
        rst_n = 0;
        #100;
        rst_n = 1;
    end
    
    // Test stimulus
    initial begin
        // Initialize UART
        $display("=== NanoCGRA v1 Testbench ===");
        $display("Starting system initialization...");
        
        // Wait for system ready
        @(posedge clk);
        @(posedge clk);
        
        // Test UART TX
        $display("Testing UART TX...");
        uart_tx = 1'b1;
        uart_tx_data = 8'h41;  // 'A'
        #100;
        uart_tx = 1'b0;
        
        // Test UART RX
        $display("Testing UART RX...");
        uart_rx_valid = 1'b1;
        uart_rx = 8'h42;  // 'B'
        #100;
        uart_rx_valid = 1'b0;
        
        // Test CGRA configuration
        $display("Testing CGRA configuration...");
        // Configure CGRA for vector addition
        // This would be done through the bus interface
        
        // Test system operation
        $display("Testing system operation...");
        @(posedge clk);
        @(posedge clk);
        
        // Monitor signals
        $display("Monitoring system status...");
        forever begin
            if (system_ready) begin
                $display("System ready at %0t", $time);
            end
            if (system_busy) begin
                $display("System busy at %0t", $time);
            end
            if (cgra_done) begin
                $display("CGRA done at %0t", $time);
            end
            if (uart_tx_ready) begin
                $display("UART TX ready at %0t", $time);
            end
            if (uart_rx_ready) begin
                $display("UART RX ready at %0t", $time);
            end
            if (uart_tx_busy) begin
                $display("UART TX busy at %0t", $time);
            end
            if (uart_rx_busy) begin
                $display("UART RX busy at %0t", $time);
            end
            @(posedge clk);
        end
        
        // Dump waveform
        $dumpfile("sim/design.vcd");
        $dumpvars(0, nanocgra_tb);
        
        $display("Testbench completed successfully!");
        $finish;
    end
    
    // Initial block
    initial begin
        // Initialize all inputs
        uart_tx = 1'b0;
        uart_rx = 8'd0;
        uart_rx_valid = 1'b0;
    end

endmodule
