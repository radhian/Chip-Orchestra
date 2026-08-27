import subprocess
# The DUT TX completes all 900 transmissions (tx_done=900).
# The TB receiver captures 814 and then hangs.
# After capturing 814, the DUT TX has already finished (tx_done=900).
# So the remaining 86 bytes were transmitted but the receiver missed them.

# The key insight: the receiver misses bytes because after receiving byte N,
# it waits for the stop bit (BAUD_DIV cycles), then looks for the next start bit.
# But the DUT TX might have already sent the start bit during the stop bit wait.

# Let me check the exact timing. The DUT TX:
# - STOP state: 1 baud period (tx_out=1)
# - IDLE state: 1 baud period (tx_out=1) if start_req, else stays
# - START state: 1 baud period (tx_out=0)
# So between two bytes, there are 2 baud periods of tx_out=1 (STOP + IDLE).

# The TB receiver:
# - After 8 data bits, waits BAUD_DIV for stop bit
# - Then while(data_o===1'b1) waits for start bit
# The stop bit wait is 1 baud period. The DUT TX has 2 baud periods of idle.
# So the TB receiver should have 1 baud period to catch the start bit.

# But wait - the DUT TX might NOT have an IDLE gap if start_req is already set!
# Let me re-read the TX FSM:
# STOP: tx_out=1, tx_done=1, state=IDLE  (on baud_tick)
# IDLE: if start_req, tx_out=0, state=START  (on baud_tick)
#       else tx_out=1
# So there IS always 1 baud period of IDLE. The STOP and IDLE are separate states.
# STOP takes 1 baud_tick, IDLE takes 1 baud_tick. So 2 baud periods of tx_out=1.

# The TB receiver waits 1 baud period for stop bit. Then it has 1 baud period
# of IDLE to detect the start bit. This should be enough.

# Unless the TB receiver's stop bit wait is misaligned with the DUT TX's stop bit.
# Let me think about this more carefully.

# The TB receiver detects the start bit at some posedge clk. Due to NBA,
# this is 1 cycle after the actual falling edge. Let's say the DUT TX start bit
# begins at cycle T. The TB receiver detects it at cycle T+1.
# The TB receiver then waits HALF_BAUD + BAUD_DIV = 651 cycles.
# So it samples bit 0 at cycle T+1+651 = T+652.
# The DUT TX: start bit is cycles T to T+433. Bit 0 is T+434 to T+867.
# At T+652, we're at 652-434=218 cycles into bit 0. Good.
# Bit 1: T+868 to T+1301. TB samples at T+652+434=T+1086. 1086-868=218 into bit 1. Good.
# ...continues aligned.
# Bit 7: T+3472+434*7 = T+3472 to T+3905. Wait, let me recalculate.
# Start: T to T+433 (434 cycles)
# Bit 0: T+434 to T+867
# Bit 1: T+868 to T+1301
# Bit 2: T+1302 to T+1735
# Bit 3: T+1736 to T+2169
# Bit 4: T+2170 to T+2603
# Bit 5: T+2604 to T+3037
# Bit 6: T+3038 to T+3471
# Bit 7: T+3472 to T+3905
# Stop: T+3906 to T+4339
# IDLE: T+4340 to T+4773
# Next start: T+4774

# TB receiver samples:
# Bit 0: T+652 (218 into bit 0) ✓
# Bit 1: T+1086 (218 into bit 1) ✓
# ...
# Bit 7: T+652+434*7 = T+3690. Bit 7 is T+3472 to T+3905. 3690-3472=218. ✓
# Stop wait: T+3690+434 = T+4124. Stop is T+3906 to T+4339. 4124 is in stop. ✓
# After stop wait: T+4124. Next start is T+4774. 
# TB receiver checks data_o at T+4124. DUT TX is in stop (tx_out=1). 
# TB receiver enters while(data_o===1'b1) loop. Waits.
# At T+4340, DUT TX goes to IDLE (tx_out=1). TB still waiting.
# At T+4774, DUT TX goes to START (tx_out=0). TB detects it at T+4775.
# TB waits 651 cycles. Samples bit 0 at T+4775+651=T+5426.
# DUT TX next frame: start T+4774, bit 0 at T+5208 to T+5641.
# 5426-5208=218. ✓

# So the timing is perfectly aligned! The receiver should catch every byte.
# But it doesn't. 86 bytes are missed.

# Let me check if the issue is that the DUT TX doesn't always have an IDLE gap.
# What if the controller asserts tx_start while the TX is still in STOP?
# The TX latches tx_start. Then after STOP, it goes to IDLE.
# In IDLE, start_req is already 1. On the next baud_tick, it goes to START.
# So there IS 1 baud period of IDLE. 

# But what if the controller pops from queue and asserts tx_start in TX_IDLE,
# and the TX module is already in IDLE (not STOP)? Then:
# Controller: TX_WAIT -> (tx_done) -> TX_IDLE -> (q_pop, tx_start) -> TX_WAIT
# TX module: was in STOP, tx_done pulses. Controller sees tx_done, goes to TX_IDLE.
# Next cycle: controller in TX_IDLE, q_pop, asserts tx_start.
# TX module: latches tx_start. On next baud_tick, goes from IDLE to START.
# But the TX module might still be in STOP when tx_start is asserted!
# TX module STOP: on baud_tick, sets tx_done=1, state=IDLE.
# Controller: sees tx_done (same cycle), goes to TX_IDLE.
# Next cycle: controller in TX_IDLE, q_pop, tx_start=1.
# TX module: in IDLE (just transitioned from STOP). Latches tx_start.
# On next baud_tick: IDLE, start_req=1, goes to START.
# So there's 1 baud period of IDLE. OK.

# But what if the queue has many entries and the controller pops rapidly?
# No, the controller only pops when in TX_IDLE, and goes to TX_WAIT after pop.
# It stays in TX_WAIT until tx_done. So it's 1 pop per TX frame.

# I'm really confused. Let me try a different approach: make the TB receiver
# NOT wait for the stop bit, and see if that fixes it.

# Actually, let me check if the issue is that the TB receiver's stop bit wait
# causes it to miss the start bit when the DUT TX has no IDLE gap.
# What if the DUT TX goes from STOP directly to START without IDLE?

# Looking at the TX code again:
# STOP: begin tx_out <= 1'b1; tx_done <= 1'b1; state <= IDLE; end
# IDLE: begin if (start_req) begin ... state <= START; ... end else tx_out <= 1'b1; end
# So STOP always goes to IDLE. IDLE always takes 1 baud_tick.
# There's always 1 baud period of IDLE. 

# But wait - what if start_req is set DURING the STOP state?
# The TX module latches tx_start on ANY clock, not just baud_tick.
# So if the controller asserts tx_start while TX is in STOP,
# start_req is set. Then STOP -> IDLE (on baud_tick). 
# In IDLE, start_req=1, so on the next baud_tick, goes to START.
# So there's still 1 baud period of IDLE.

# OK let me just try removing the stop bit wait from the TB receiver
# and see if that helps.

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

    // Modified receiver: no stop bit wait
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
            // No stop bit wait - go straight to looking for next start bit
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