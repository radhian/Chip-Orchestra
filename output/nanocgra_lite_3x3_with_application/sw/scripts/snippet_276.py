import subprocess
# Let's create a minimal testbench to debug the issue
# First, let's check if the DUT produces all 900 results by using a smaller BAUD_DIV
# and a simpler testbench that doesn't use real baud timing

testbench = '''`include "params.vh"
`timescale 1ns/1ps

module nano_cgra_3x3_sobel_accelerator_v4_tb;

    reg clk;
    reg rst_async_n;
    reg data_i;
    wire data_o;

    nano_cgra_3x3_sobel_accelerator_v4 dut (
        .clk(clk),
        .rst_async_n(rst_async_n),
        .data_i(data_i),
        .data_o(data_o)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    localparam integer BAUD_DIV = `BAUD_DIV;
    localparam integer HALF_BAUD = BAUD_DIV / 2;
    localparam integer N_PIXELS = 1024;
    localparam integer N_RESULTS = 900;

    reg [7:0] input_img [0:1023];
    reg [7:0] golden_out [0:899];
    reg [7:0] chip_out [0:899];
    integer n_captured;
    integer i;
    integer errors;
    reg [7:0] rx_byte;

    task send_byte;
        input [7:0] byte_val;
        integer b;
        begin
            data_i = 1'b0;
            repeat (BAUD_DIV) @(posedge clk);
            for (b = 0; b < 8; b = b + 1) begin
                data_i = byte_val[b];
                repeat (BAUD_DIV) @(posedge clk);
            end
            data_i = 1'b1;
            repeat (BAUD_DIV) @(posedge clk);
        end
    endtask

    task recv_byte_blocking;
        output [7:0] byte_val;
        integer b;
        begin
            byte_val = 8'd0;
            while (data_o === 1'b1) @(posedge clk);
            repeat (HALF_BAUD + BAUD_DIV) @(posedge clk);
            for (b = 0; b < 8; b = b + 1) begin
                byte_val[b] = data_o;
                repeat (BAUD_DIV) @(posedge clk);
            end
            repeat (BAUD_DIV) @(posedge clk);
        end
    endtask

    initial begin
        $readmemh("rtl/sobel_input.mem", input_img);
        $readmemh("waves/golden_output.mem", golden_out);

        rst_async_n = 0;
        data_i = 1'b1;
        n_captured = 0;
        errors = 0;

        repeat (10) @(posedge clk);
        rst_async_n = 1;
        repeat (5) @(posedge clk);

        $display("Starting test with %0d pixels...", N_PIXELS);

        fork
            begin
                for (i = 0; i < N_PIXELS; i = i + 1) begin
                    send_byte(input_img[i]);
                end
                $display("All pixels sent at time %0t", $time);
            end
            begin
                while (n_captured < N_RESULTS) begin
                    recv_byte_blocking(rx_byte);
                    chip_out[n_captured] = rx_byte;
                    n_captured = n_captured + 1;
                    if (n_captured % 100 == 0)
                        $display("  Captured %0d results at time %0t", n_captured, $time);
                end
                $display("All %0d results captured at time %0t", n_captured, $time);
            end
        join

        $writememh("waves/chip_output.mem", chip_out);
        $display("Captured %0d results", n_captured);
        $display("First 10 chip: %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h",
            chip_out[0], chip_out[1], chip_out[2], chip_out[3], chip_out[4],
            chip_out[5], chip_out[6], chip_out[7], chip_out[8], chip_out[9]);
        $display("First 10 gold: %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h",
            golden_out[0], golden_out[1], golden_out[2], golden_out[3], golden_out[4],
            golden_out[5], golden_out[6], golden_out[7], golden_out[8], golden_out[9]);

        if (n_captured != N_RESULTS) begin
            $display("FAIL: captured %0d, expected %0d", n_captured, N_RESULTS);
        end

        for (i = 0; i < n_captured && i < N_RESULTS; i = i + 1) begin
            if (chip_out[i] !== golden_out[i]) begin
                $display("MISMATCH at %0d: chip=0x%02h golden=0x%02h", i, chip_out[i], golden_out[i]);
                errors = errors + 1;
                if (errors > 20) i = N_RESULTS;
            end
        end

        if (errors == 0 && n_captured == N_RESULTS) begin
            $display("TEST PASSED");
        end else begin
            $display("TEST FAILED with %0d errors", errors);
        end
        $finish;
    end

    initial begin
        repeat (200000000) @(posedge clk);
        $display("TIMEOUT at time %0t, captured %0d", $time, n_captured);
        $finish;
    end

endmodule
'''

with open('tb/debug_tb.v', 'w') as f:
    f.write(testbench)

result = subprocess.run(['sh','-c','iverilog -g2012 -o work/debug.vvp -Irtl -s nano_cgra_3x3_sobel_accelerator_v4_tb rtl/*.v tb/debug_tb.v && vvp work/debug.vvp'], capture_output=True, text=True, timeout=600)
print("STDOUT:", result.stdout[-3000:])
print("STDERR:", result.stderr[-1000:])