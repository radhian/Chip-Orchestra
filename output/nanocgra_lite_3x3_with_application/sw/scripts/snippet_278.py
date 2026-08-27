import subprocess
# q_push_count=900, so all 900 results ARE pushed to the queue.
# But only 814 are captured. q_count=0 at timeout, meaning the queue is empty.
# So the DUT transmitted 814 results but the TB only captured 814.
# The remaining 86 results were never transmitted (or were transmitted but not captured).

# Wait - q_count=0 at timeout means the queue is empty. But q_push=900 and only 814 captured.
# That means 900-814=86 results were popped from the queue but not captured by the TB.
# OR they were popped and transmitted but the TB receiver missed them.

# Actually, the TX FSM pops from queue and sends via UART. If 900 were pushed and 
# q_count=0 at end, then 900 were popped. But only 814 were captured.
# So 86 results were transmitted but not captured by the TB receiver.

# This could be a timing issue: the TB receiver might miss start bits,
# or the DUT TX might send bytes too fast for the TB receiver.

# Let me check: the DUT TX resets baud_cnt when starting a new frame.
# The TB receiver waits for the falling edge (start bit), then samples
# at HALF_BAUD + BAUD_DIV from the falling edge.
# But the TB receiver samples at posedge clk, while the DUT TX changes tx_out
# at posedge clk (on baud_tick). There might be a race condition.

# Actually, the TB receiver does: while (data_o === 1'b1) @(posedge clk);
# This detects the falling edge. But data_o is set by the DUT TX at posedge clk.
# So at the posedge where tx_out goes low (start bit), the TB sees data_o=1 (old value)
# because of the non-blocking assignment. The TB will see data_o=0 on the NEXT posedge.
# Then it waits HALF_BAUD + BAUD_DIV = 217+434 = 651 cycles.
# This should put it in the middle of the first data bit.
# The DUT TX start bit lasts 434 cycles (baud_cnt reset to 0).
# Then bit 0 lasts 434 cycles. So the first data bit starts at cycle 434 after start.
# The TB samples at 651 cycles after detecting start, which is in the middle of bit 0.
# This should be fine.

# But wait - the DUT TX resets baud_cnt when going IDLE->START.
# This means the start bit is exactly 434 cycles. Then each subsequent bit is 434 cycles.
# The TB receiver samples every 434 cycles after the initial offset.
# This should be aligned.

# Let me check if the issue is that the DUT TX sends the last 86 results
# AFTER the TB sender finishes, and the TB receiver is still waiting.
# But the TB receiver should keep running until it captures all 900.
# The fork/join waits for both processes. The receiver loop runs until n_captured=900.
# If the DUT stops transmitting after 814, the receiver hangs.

# But q_count=0 means all 900 were popped. So the DUT DID transmit all 900.
# The TB receiver must have missed 86 of them.

# Let me check if there's a timing issue where the TB receiver misses
# a start bit because it's still processing the previous byte.

# The TB receiver: after receiving a byte, it does repeat(BAUD_DIV) for stop bit.
# Then loops back to while(data_o === 1'b1) @(posedge clk).
# If the DUT TX starts the next byte immediately after the stop bit,
# the TB receiver might miss the start bit falling edge.

# The DUT TX: after STOP state, goes to IDLE. In IDLE, if start_req, goes to START.
# The TB receiver: after sampling 8 data bits, does repeat(BAUD_DIV) for stop bit.
# Then checks while(data_o === 1'b1). If the DUT TX already started the next byte,
# data_o might already be 0 (start bit), and the TB receiver catches it.
# But if the DUT TX is still in IDLE (tx_out=1), the TB receiver waits.

# The issue might be: the DUT TX sends byte N, then immediately starts byte N+1.
# The TB receiver finishes byte N, waits for stop bit, then looks for start bit.
# But the DUT TX might have already started byte N+1's start bit DURING
# the TB receiver's stop bit wait. So the TB receiver misses the start bit.

# Let me check the timing:
# DUT TX: STOP state -> tx_out=1, tx_done=1, state=IDLE. This is 1 baud_tick.
# Next baud_tick: IDLE state, if start_req, tx_out=0 (start bit), state=START.
# So there's 1 baud period (434 cycles) of idle (tx_out=1) between frames.
# The TB receiver: after 8 data bits, does repeat(BAUD_DIV) for stop bit = 434 cycles.
# Then while(data_o===1'b1) - if DUT TX is in IDLE (tx_out=1), it waits.
# When DUT TX goes to START (tx_out=0), TB receiver detects it.
# This should work... unless the DUT TX goes to START during the TB's stop bit wait.

# Actually, the DUT TX stop bit is 1 baud period. The TB receiver also waits
# 1 baud period for the stop bit. So they should be aligned.
# After the stop bit, DUT TX goes to IDLE for at least 1 baud_tick.
# The TB receiver finishes the stop bit wait and checks data_o.
# If DUT TX is in IDLE (tx_out=1), TB waits for the next start bit.
# This should work.

# But there's a subtlety: the DUT TX baud_cnt is free-running after reset.
# After STOP, baud_cnt continues. In IDLE, it waits for baud_tick.
# The TB receiver is also counting cycles. If they get out of sync...

# Actually, let me just check if the issue is that the TB receiver's
# initial offset (HALF_BAUD + BAUD_DIV) is wrong.
# The TB receiver detects start bit at some posedge.
# Then waits HALF_BAUD + BAUD_DIV = 651 cycles.
# The DUT TX start bit is 434 cycles. First data bit is 434 cycles.
# So at 651 cycles, we're at 651-434=217 cycles into the first data bit.
# 217 is half of 434, so we're in the middle of bit 0. Good.
# Then samples every 434 cycles. This should stay aligned.

# Let me try a different approach: check if the DUT TX is actually
# transmitting all 900 bytes by counting tx_done pulses.

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
    integer n_captured;
    integer i;
    integer tx_done_count;
    integer tx_start_count;

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

    always @(posedge clk) begin
        if (dut.u_uart_tx.tx_done) begin
            tx_done_count = tx_done_count + 1;
        end
        if (dut.u_ctrl.tx_start) begin
            tx_start_count = tx_start_count + 1;
        end
    end

    initial begin
        $readmemh("rtl/sobel_input.mem", input_img);

        rst_async_n = 0;
        data_i = 1'b1;
        n_captured = 0;
        tx_done_count = 0;
        tx_start_count = 0;

        repeat (10) @(posedge clk);
        rst_async_n = 1;
        repeat (5) @(posedge clk);

        fork
            begin
                for (i = 0; i < N_PIXELS; i = i + 1) begin
                    send_byte(input_img[i]);
                end
                $display("All pixels sent. tx_start=%0d tx_done=%0d", tx_start_count, tx_done_count);
            end
            begin
                // Just wait and monitor
                repeat (50000000) @(posedge clk);
                $display("After 50M cycles: tx_start=%0d tx_done=%0d q_count=%0d q_push=%0d", 
                    tx_start_count, tx_done_count, dut.u_ctrl.q_count, dut.u_ctrl.q_push);
            end
        join

        $finish;
    end

    initial begin
        repeat (200000000) @(posedge clk);
        $display("TIMEOUT: tx_start=%0d tx_done=%0d q_count=%0d", 
            tx_start_count, tx_done_count, dut.u_ctrl.q_count);
        $finish;
    end

endmodule
'''

with open('tb/debug_tb.v', 'w') as f:
    f.write(testbench)

result = subprocess.run(['sh','-c','iverilog -g2012 -o work/debug.vvp -Irtl -s nano_cgra_3x3_sobel_accelerator_v4_tb rtl/*.v tb/debug_tb.v && vvp work/debug.vvp'], capture_output=True, text=True, timeout=600)
print("STDOUT:", result.stdout[-3000:])
print("STDERR:", result.stderr[-1000:])