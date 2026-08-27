import subprocess
# The DUT captures 814 results, not 900. 86 results are missing.
# The queue depth is now 256, so queue overflow shouldn't be the issue.
# Let's check if the DUT actually produces all 900 results.
# Let's add monitoring to the controller's q_push and q_count.

# Let's create a testbench that monitors the internal signals
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
    reg [7:0] chip_out [0:899];
    integer n_captured;
    integer i;
    integer errors;
    reg [7:0] rx_byte;

    // Monitor signals
    integer q_push_count;
    integer rx_valid_count;

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

    // Monitor q_push and rx_valid
    always @(posedge clk) begin
        if (dut.u_ctrl.rx_valid) begin
            rx_valid_count = rx_valid_count + 1;
        end
        if (dut.u_ctrl.q_push) begin
            q_push_count = q_push_count + 1;
        end
    end

    initial begin
        $readmemh("rtl/sobel_input.mem", input_img);

        rst_async_n = 0;
        data_i = 1'b1;
        n_captured = 0;
        errors = 0;
        q_push_count = 0;
        rx_valid_count = 0;

        repeat (10) @(posedge clk);
        rst_async_n = 1;
        repeat (5) @(posedge clk);

        fork
            begin
                for (i = 0; i < N_PIXELS; i = i + 1) begin
                    send_byte(input_img[i]);
                end
                $display("All pixels sent. rx_valid_count=%0d q_push_count=%0d", rx_valid_count, q_push_count);
            end
            begin
                while (n_captured < N_RESULTS) begin
                    recv_byte_blocking(rx_byte);
                    chip_out[n_captured] = rx_byte;
                    n_captured = n_captured + 1;
                    if (n_captured % 100 == 0)
                        $display("  Captured %0d, q_push_count=%0d, q_count=%0d", n_captured, q_push_count, dut.u_ctrl.q_count);
                end
            end
        join

        $display("Final: captured=%0d rx_valid=%0d q_push=%0d", n_captured, rx_valid_count, q_push_count);
        $finish;
    end

    initial begin
        repeat (200000000) @(posedge clk);
        $display("TIMEOUT: captured=%0d rx_valid=%0d q_push=%0d q_count=%0d", 
            n_captured, rx_valid_count, q_push_count, dut.u_ctrl.q_count);
        $finish;
    end

endmodule
'''

with open('tb/debug_tb.v', 'w') as f:
    f.write(testbench)

result = subprocess.run(['sh','-c','iverilog -g2012 -o work/debug.vvp -Irtl -s nano_cgra_3x3_sobel_accelerator_v4_tb rtl/*.v tb/debug_tb.v && vvp work/debug.vvp'], capture_output=True, text=True, timeout=600)
print("STDOUT:", result.stdout[-3000:])
print("STDERR:", result.stderr[-1000:])