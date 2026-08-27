import subprocess
# tx_start=900, tx_done=900. So the DUT DID transmit all 900 bytes.
# But the TB receiver only captured 814. So 86 bytes were transmitted
# but the TB receiver missed them.

# The issue is in the TB receiver's byte detection. Let me check if
# the TB receiver misses start bits because it's still in the stop bit
# wait when the next start bit arrives.

# The DUT TX: after STOP, goes to IDLE. In IDLE, on next baud_tick,
# if start_req, goes to START (tx_out=0). 
# But the DUT controller pops from queue and asserts tx_start.
# The TX module latches tx_start. Then on next baud_tick, starts.
# So there's at least 1 baud period between frames (the IDLE state).
# But the IDLE state might be 0 baud periods if start_req is already set
# when entering IDLE.

# Actually, looking at the TX FSM:
# STOP: tx_out=1, tx_done=1, state=IDLE  (on baud_tick)
# IDLE: if start_req, tx_out=0, state=START  (on next baud_tick)
# So there's exactly 1 baud period of IDLE (tx_out=1) between STOP and START.
# The TB receiver: after 8 data bits, does repeat(BAUD_DIV) for stop bit.
# That's 434 cycles. Then while(data_o===1'b1) @(posedge clk).
# The DUT TX stop bit is also 434 cycles. So the TB receiver finishes
# the stop bit wait at the same time the DUT TX finishes STOP.
# Then DUT TX goes to IDLE for 1 baud period (tx_out=1).
# The TB receiver checks data_o - it's 1, so it waits.
# Then DUT TX goes to START (tx_out=0). TB receiver detects it.
# This should work.

# But wait - the DUT TX resets baud_cnt when going IDLE->START.
# This means the start bit is exactly 434 cycles.
# But the TB receiver detects the start bit at a posedge, then waits
# HALF_BAUD + BAUD_DIV = 651 cycles. 
# The detection happens 1 cycle after the actual falling edge (due to NBA).
# So the TB receiver starts counting 1 cycle after the start bit begins.
# At 651 cycles, it's at 650 cycles into the frame.
# Start bit = 434 cycles. First data bit starts at 434.
# 650 - 434 = 216 cycles into first data bit. That's fine (middle of bit).

# But here's the issue: the TB receiver detects the start bit by polling
# data_o at posedge clk. The DUT TX changes tx_out at posedge clk (on baud_tick).
# Due to non-blocking assignment, the TB receiver sees the OLD value of tx_out
# at the same posedge. So the TB receiver detects the start bit 1 cycle late.
# This 1-cycle delay is constant, so it shouldn't cause problems.

# Let me think about this differently. The DUT transmits 900 bytes.
# The TB receiver captures 814. 86 are missed.
# 86 is close to 900-814=86. Let me check if there's a pattern.

# Actually, let me check if the issue is that the TB receiver's stop bit
# wait is too long, causing it to miss the next start bit.
# The DUT TX: STOP is 1 baud period (434 cycles). Then IDLE is 1 baud period.
# Total gap between last data bit and next start bit: 2 baud periods = 868 cycles.
# The TB receiver: after last data bit, waits BAUD_DIV=434 for stop bit.
# Then checks data_o. If DUT TX is in IDLE (tx_out=1), waits for start bit.
# The DUT TX IDLE lasts 434 cycles. So the TB receiver should catch the start bit.

# Hmm, but what if the DUT TX IDLE is 0 cycles? I.e., start_req is already
# set when STOP transitions to IDLE. Then on the next baud_tick, it goes
# straight to START. So the gap is only 1 baud period (STOP), not 2.
# The TB receiver waits 434 for stop bit. Then checks data_o.
# If the DUT TX already went to START (tx_out=0), the TB receiver catches it.
# But if the DUT TX is still in STOP/IDLE transition...

# Actually, the DUT TX STOP and IDLE are both 1 baud_tick each.
# STOP: on baud_tick, set tx_out=1, tx_done=1, state=IDLE.
# IDLE: on next baud_tick, if start_req, set tx_out=0, state=START.
# So there are 2 baud_ticks between the last data bit and the start bit.
# The TB receiver waits 1 baud period (434 cycles) for stop bit.
# Then it's at the same point as the DUT TX's IDLE state.
# The DUT TX IDLE lasts 434 cycles. The TB receiver polls data_o.
# When DUT TX goes to START (tx_out=0), TB receiver detects it.
# This should work.

# Wait, I need to check: does the DUT TX actually have an IDLE gap?
# Let me re-read the TX FSM:
# STOP: tx_out=1, tx_done=1, state=IDLE  (on baud_tick)
# IDLE: if start_req, tx_out=0, state=START  (on baud_tick)
#       else tx_out=1
# So yes, there's 1 baud period of IDLE between STOP and START.
# But the TB receiver's stop bit wait is also 1 baud period.
# So the TB receiver finishes stop bit wait when DUT TX is in IDLE.
# Then TB receiver polls and catches the start bit. Should work.

# Let me try a different approach: make the TB receiver more robust
# by checking for the start bit immediately after the stop bit,
# without the extra repeat(BAUD_DIV).

# Actually, let me check if the issue is that the TB receiver's
# stop bit wait causes it to miss the start bit when the DUT TX
# has no IDLE gap (back-to-back transmission).

# If the DUT TX goes from STOP directly to START (no IDLE gap),
# the gap is only 1 baud period. The TB receiver waits 1 baud period
# for the stop bit. By then, the DUT TX is already in START (tx_out=0).
# The TB receiver checks data_o - it's 0. But the while loop condition
# is while(data_o === 1'b1). Since data_o is 0, it doesn't enter the loop.
# It proceeds to sample. But it missed the start bit detection!
# It thinks it's already in the data phase.

# Wait, no. The TB receiver's flow is:
# 1. while (data_o === 1'b1) @(posedge clk);  -- wait for start bit
# 2. repeat (HALF_BAUD + BAUD_DIV) @(posedge clk);  -- wait to middle of bit 0
# 3. Sample 8 bits
# 4. repeat (BAUD_DIV) @(posedge clk);  -- stop bit
# 5. Go back to 1.

# If the DUT TX sends back-to-back (STOP immediately followed by START),
# then after step 4 (stop bit wait), data_o might already be 0 (next start bit).
# Step 1: while(data_o === 1'b1) - data_o is 0, so it doesn't wait.
# It immediately proceeds to step 2. But it's already in the start bit!
# It waits HALF_BAUD + BAUD_DIV = 651 cycles. 
# The start bit is 434 cycles. So at 651 cycles, it's 217 cycles into bit 0.
# That's correct! So back-to-back should work.

# But wait - the DUT TX does have an IDLE gap (1 baud period).
# So after the TB receiver's stop bit wait (434 cycles), the DUT TX is in IDLE.
# The TB receiver checks data_o - it's 1 (IDLE). It waits.
# Then DUT TX goes to START. TB receiver detects it.
# This should work.

# I'm confused about why 86 bytes are missed. Let me try a completely
# different approach: use a much smaller BAUD_DIV for testing.

# Actually, the real problem might be that the simulation is just too slow
# with BAUD_DIV=434. 900 results * 10 * 434 = 3.9M cycles for TX.
# 1024 pixels * 10 * 434 = 4.4M cycles for RX.
# Total with concurrency: ~5M cycles. At 10ns per cycle, that's 50ms sim time.
# But the watchdog is 100M cycles = 1s sim time. That should be enough.

# Wait, the debug TB showed: all 900 tx_done at 50M cycles.
# But the receiver only got 814. And the sim ran to 200M cycles.
# So the receiver had 150M cycles to catch the remaining 86 bytes.
# But it didn't. The DUT TX had already finished (tx_done=900).
# So the DUT TX transmitted all 900, but the receiver missed 86.

# This means the receiver is missing bytes during reception.
# Let me check if there's a race condition in the receiver.

# Actually, I bet the issue is that the DUT TX sends back-to-back bytes
# without the IDLE gap in some cases. Let me check the TX FSM again.
# The controller: TX_WAIT -> (tx_done) -> TX_IDLE -> (q_pop) -> TX_WAIT
# In TX_IDLE, if q_pop, it asserts tx_start and goes to TX_WAIT.
# The TX module latches tx_start. Then on next baud_tick, starts.
# But the TX module might still be in STOP state when the controller
# asserts tx_start. The TX module latches it, then after STOP goes to IDLE,
# and on next baud_tick, starts. So there IS an IDLE gap.

# But what if the queue has multiple entries? The controller pops one,
# sends it, waits for tx_done, pops the next. So it's sequential.
# Each TX takes 10 baud periods + 1 IDLE baud period = 11 baud periods.
# The TB receiver expects 10 baud periods per byte (start + 8 data + stop).
# The extra IDLE period means the TB receiver has extra time.
# So it should never miss a start bit.

# Unless... the TB receiver's timing drifts. Let me check.
# The TB receiver detects start bit, then waits HALF_BAUD + BAUD_DIV.
# Then samples every BAUD_DIV. 
# If the DUT TX's baud period is exactly BAUD_DIV, this is fine.
# But the DUT TX resets baud_cnt when starting. So the start bit is
# exactly BAUD_DIV cycles. Then each subsequent bit is BAUD_DIV cycles.
# The TB receiver samples at HALF_BAUD + BAUD_DIV, then every BAUD_DIV.
# So the first sample is at 651 cycles (middle of bit 0).
# Subsequent samples at 651+434=1085 (middle of bit 1), etc.
# This should be perfectly aligned.

# I'm stuck. Let me just try with a smaller BAUD_DIV to see if it's
# a timing issue or a logic issue.

testbench = '''`include "params.vh"
`timescale 1ns/1ps

module nano_cgra_3x3_sobel_accelerator_v4_tb;

    reg clk;
    reg rst_async_n;
    reg data_i;
    wire data_o;

    // Override BAUD_DIV for faster simulation
    localparam integer FAST_BAUD = 8;

    nano_cgra_3x3_sobel_accelerator_v4 dut (
        .clk(clk),
        .rst_async_n(rst_async_n),
        .data_i(data_i),
        .data_o(data_o)
    );

    // Override the baud divider inside the DUT
    // This doesn't work with iverilog directly, but we can use defparam
    // Actually, the BAUD_DIV is a macro, not a parameter. Can't override.
    // Let's just use the real baud but with a tighter watchdog.

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
    integer tx_done_count;

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

    always @(posedge clk) begin
        if (dut.u_uart_tx.tx_done) begin
            tx_done_count = tx_done_count + 1;
        end
    end

    initial begin
        $readmemh("rtl/sobel_input.mem", input_img);
        $readmemh("waves/golden_output.mem", golden_out);

        rst_async_n = 0;
        data_i = 1'b1;
        n_captured = 0;
        errors = 0;
        tx_done_count = 0;

        repeat (10) @(posedge clk);
        rst_async_n = 1;
        repeat (5) @(posedge clk);

        fork
            begin
                for (i = 0; i < N_PIXELS; i = i + 1) begin
                    send_byte(input_img[i]);
                end
            end
            begin
                while (n_captured < N_RESULTS) begin
                    recv_byte_blocking(rx_byte);
                    chip_out[n_captured] = rx_byte;
                    n_captured = n_captured + 1;
                    if (n_captured % 100 == 0)
                        $display("  Captured %0d, tx_done=%0d", n_captured, tx_done_count);
                end
            end
        join

        $display("Captured %0d, tx_done=%0d", n_captured, tx_done_count);
        $display("First 10 chip: %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h",
            chip_out[0], chip_out[1], chip_out[2], chip_out[3], chip_out[4],
            chip_out[5], chip_out[6], chip_out[7], chip_out[8], chip_out[9]);
        $display("First 10 gold: %0h %0h %0h %0h %0h %0h %0h %0h %0h %0h",
            golden_out[0], golden_out[1], golden_out[2], golden_out[3], golden_out[4],
            golden_out[5], golden_out[6], golden_out[7], golden_out[8], golden_out[9]);

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
            $display("TEST FAILED: %0d errors, captured %0d/%0d", errors, n_captured, N_RESULTS);
        end
        $finish;
    end

    initial begin
        repeat (200000000) @(posedge clk);
        $display("TIMEOUT: captured=%0d tx_done=%0d", n_captured, tx_done_count);
        $finish;
    end

endmodule
'''

with open('tb/debug_tb.v', 'w') as f:
    f.write(testbench)

result = subprocess.run(['sh','-c','iverilog -g2012 -o work/debug.vvp -Irtl -s nano_cgra_3x3_sobel_accelerator_v4_tb rtl/*.v tb/debug_tb.v && vvp work/debug.vvp'], capture_output=True, text=True, timeout=600)
print("STDOUT:", result.stdout[-3000:])
print("STDERR:", result.stderr[-1000:])