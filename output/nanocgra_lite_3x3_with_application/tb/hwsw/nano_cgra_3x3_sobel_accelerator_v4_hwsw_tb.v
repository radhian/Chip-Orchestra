// nano_cgra_3x3_sobel_accelerator_v4_hwsw_tb — HW/SW co-verification interface bench (generated).
// Derived from tb/nano_cgra_3x3_sobel_accelerator_v4_tb.v, the top-level testbench that passed SIM,
// so the physical protocol (frame format, baud timing, sender/receiver
// structure) is the one the chip is already known to speak.
//
// What changed: the stimulus is whatever the Python host driver encoded from
// the user's input (hwsw/stimulus.mem), the expected values are the golden
// model's answer for THAT SAME input (hwsw/expected_output.mem), and the chip's
// response is dumped to hwsw/chip_output.mem for the driver to decode.

// tb/nano_cgra_3x3_sobel_accelerator_v4_hwsw_tb.v — MAIN testbench.
// Top module: nano_cgra_3x3_sobel_accelerator_v4
// Streams a 32x32 image via UART, captures 30x30 Sobel results via UART,
// and compares against hwsw/expected_output.mem.
//
// The sender and receiver run CONCURRENTLY using fork/join so that
// results transmitted by the DUT while pixels are still being sent
// are captured without missing start bits.
`include "params.vh"

`timescale 1ns/1ps

module nano_cgra_3x3_sobel_accelerator_v4_hwsw_tb;

    // ---- DUT signals ----
    reg clk;
    reg rst_async_n;
    reg data_i;
    wire data_o;

    // ---- DUT ----
    nano_cgra_3x3_sobel_accelerator_v4 dut (
        .clk(clk),
        .rst_async_n(rst_async_n),
        .data_i(data_i),
        .data_o(data_o)
    );

    // ---- Clock ----
    initial clk = 0;
    always #5 clk = ~clk;

    // ---- Constants ----
    localparam integer BAUD_DIV = `BAUD_DIV;       // 434
    localparam integer HALF_BAUD = BAUD_DIV / 2;   // 217
    localparam integer N_PIXELS = 1024;            // 32*32
    localparam integer N_RESULTS = 900;            // 30*30

    // ---- Input image (loaded from rtl/sobel_input.mem) ----
    reg [7:0] input_img [0:1023];

    // ---- Golden output (loaded from hwsw/expected_output.mem) ----
    reg [7:0] golden_out [0:899];

    // ---- Chip output (captured from UART TX) ----
    reg [7:0] chip_out [0:899];
    integer n_captured;

    // ---- UART send task: serialize one byte onto data_i ----
    task send_byte;
        input [7:0] byte_val;
        integer b;
        begin
            // Start bit (0)
            data_i = 1'b0;
            repeat (BAUD_DIV) @(posedge clk);
            // 8 data bits, LSB first
            for (b = 0; b < 8; b = b + 1) begin
                data_i = byte_val[b];
                repeat (BAUD_DIV) @(posedge clk);
            end
            // Stop bit (1)
            data_i = 1'b1;
            repeat (BAUD_DIV) @(posedge clk);
        end
    endtask

    // ---- UART receive task: capture one byte from data_o ----
    // Waits for start bit with NO timeout (blocks until a byte arrives).
    // This is used by the concurrent receiver process.
    // After sampling the 8th data bit, immediately looks for the next
    // start bit — no stop-bit wait. This matches the golden model's
    // UART RX which transitions from DATA to STOP and immediately
    // watches for the next falling edge.
    task recv_byte_blocking;
        output [7:0] byte_val;
        integer b;
        begin
            byte_val = 8'd0;
            // Wait for start bit (data_o goes low)
            while (data_o === 1'b1) @(posedge clk);
            // Start bit detected — wait to middle of first data bit
            repeat (HALF_BAUD + BAUD_DIV) @(posedge clk);
            // Sample 8 data bits, LSB first
            for (b = 0; b < 8; b = b + 1) begin
                byte_val[b] = data_o;
                repeat (BAUD_DIV) @(posedge clk);
            end
            // No stop-bit wait: immediately look for next start bit.
            // The DUT TX always inserts 1 baud period of IDLE (tx_out=1)
            // between frames, so the while-loop above will catch it.
        end
    endtask

    // ---- Main test flow ----
    integer i;
    integer errors;
    reg [7:0] rx_byte;

    initial begin
        // ---- Load input and golden data ----
        $readmemh("hwsw/stimulus.mem", input_img);
        $readmemh("hwsw/expected_output.mem", golden_out);

        // ---- Dump waves ----
        $dumpfile("hwsw/hwsw.vcd");
        $dumpvars(0, rst_async_n, data_i, data_o);

        // ---- Initialize ----
        rst_async_n = 0;
        data_i = 1'b1;  // UART idle high
        n_captured = 0;
        errors = 0;

        // ---- Reset for a few cycles ----
        repeat (10) @(posedge clk);
        rst_async_n = 1;
        repeat (5) @(posedge clk);

        // ---- Send all 1024 pixels and capture results concurrently ----
        $display("Starting Sobel accelerator test: sending %0d pixels...", N_PIXELS);

        fork
            // Sender process: send all pixels
            begin
                for (i = 0; i < N_PIXELS; i = i + 1) begin
                    send_byte(input_img[i]);
                end
            end
            // Receiver process: capture all results
            begin
                while (n_captured < N_RESULTS) begin
                    recv_byte_blocking(rx_byte);
                    chip_out[n_captured] = rx_byte;
                    n_captured = n_captured + 1;
                    if (n_captured % 100 == 0)
                        $display("  Captured %0d results...", n_captured);
                end
            end
        join

        // ---- Write chip output to file ----
        $writememh("hwsw/chip_output.mem", chip_out);
        $display("Chip output written to hwsw/chip_output.mem (%0d values)", n_captured);

        // ---- Display key output values ----
        $display("First 10 chip outputs: %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h",
            chip_out[0], chip_out[1], chip_out[2], chip_out[3], chip_out[4],
            chip_out[5], chip_out[6], chip_out[7], chip_out[8], chip_out[9]);
        $display("First 10 golden outputs: %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h",
            golden_out[0], golden_out[1], golden_out[2], golden_out[3], golden_out[4],
            golden_out[5], golden_out[6], golden_out[7], golden_out[8], golden_out[9]);

        // ---- Compare chip output against golden output ----
        if (n_captured != N_RESULTS) begin
            $display("FAIL: captured %0d results, expected %0d", n_captured, N_RESULTS);
            $fatal(1);
        end

        for (i = 0; i < N_RESULTS; i = i + 1) begin
            if (chip_out[i] !== golden_out[i]) begin
                $display("MISMATCH at index %0d: chip=0x%02h (%0d) golden=0x%02h (%0d)",
                    i, chip_out[i], chip_out[i], golden_out[i], golden_out[i]);
                errors = errors + 1;
                if (errors > 20) begin
                    $display("Too many mismatches, stopping");
                    $fatal(1);
                end
            end
        end

        if (errors == 0) begin
            $display("TEST PASSED — all %0d Sobel outputs match golden", N_RESULTS);
        end else begin
            $display("TEST FAILED — %0d mismatches out of %0d", errors, N_RESULTS);
            $fatal(1);
        end

        $finish;
    end

    // ---- Timeout watchdog ----
    initial begin
        // 100M cycles should be more than enough
        repeat (100000000) @(posedge clk);
        $display("TIMEOUT: simulation exceeded 100M cycles");
        $fatal(1);
    end

endmodule