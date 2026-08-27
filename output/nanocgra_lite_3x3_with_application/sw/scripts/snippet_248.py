# The baud_gen counts 0..433 and ticks at 434. The TB uses BAUD_DIV=434.
# send_byte: data_i = bit; repeat(BAUD_DIV) @(posedge clk);
# So each bit period is exactly 434 clock cycles. ✓
# 
# The baud_gen ticks every 434 cycles. The UART TX/RX use baud_tick.
# The TB's bit timing matches the baud_gen. ✓
#
# But there's a subtle issue: the baud_gen and the TB are not synchronized.
# The baud_gen starts counting from reset. The TB starts sending after reset.
# The TB's first bit transition might not align with a baud_tick.
#
# For the UART RX: it detects the start bit on a baud_tick when prev_line=1 and rx_in=0.
# Then it samples data bits on subsequent baud_ticks. The sampling is at baud_tick
# boundaries, which may not be at the CENTER of the TB's bit periods.
#
# This is a standard UART timing issue. The RX detects the start bit at a baud_tick
# which could be anywhere within the TB's start bit period. Then it samples at
# baud_tick intervals. If the baud_tick is near the edge of the TB's bit periods,
# the sampling could be off by one bit.
#
# But this would affect ALL bytes, not just odd ones. The even bytes work fine.
#
# Let me think about what's different for odd vs even bytes.
# 
# After the first result (even, out[0]):
# - Controller captures, TX sends 0x44
# - TB receives 0x44 correctly
# - TB sends next pixel (10 baud)
# - Controller captures, TX sends 0x38
# - TB receives... 0x9c (wrong!)
#
# The difference between even and odd: for even, the controller was in S_RECV
# when the pixel arrived (it had been in S_RECV since the start or since the last
# tx_done). For odd, the controller had JUST transitioned from S_NEXT to S_RECV.
#
# Wait, actually the debug shows ALL results are captured and ALL tx_start fire.
# So the controller is always in S_RECV when pixels arrive. The issue is purely
# in the UART TX-to-TB timing.
#
# Let me check: maybe the TX is sending the byte at a different phase relative
# to the TB's recv_byte for odd vs even results.
#
# For even results (out[0], out[2], ...):
# - The controller was in S_RECV for a while (no recent TX)
# - The TX is idle when tx_start arrives
# - TX starts on the next baud_tick
# - TB's recv_byte catches the start bit
#
# For odd results (out[1], out[3], ...):
# - The controller just finished a TX (tx_done fired, went to S_RECV)
# - The next pixel arrives, controller captures, tx_start fires
# - But the TX might still be in the STOP state or just transitioned to IDLE
# - The TX latches tx_start and starts on the next baud_tick
# - The TB's recv_byte catches the start bit
#
# The timing should be the same. Unless the TX's baud_gen phase is different.
# 
# Actually, wait. The TX and RX share the same baud_gen? No, each has its own
# baud_gen instance. But they're both clocked by the same clk and reset.
# So their baud_ticks are aligned. ✓
#
# Let me look at this from the TB side. The TB's recv_byte:
# 1. Waits for data_o to go low (start bit)
# 2. Waits HALF_BAUD + BAUD_DIV = 1.5 baud to get to middle of first data bit
# 3. Samples 8 bits at BAUD_DIV intervals
# 4. Waits BAUD_DIV for stop bit
#
# The issue might be that the TB detects the start bit at a different point
# in the bit period for odd vs even results. If the TX starts at a different
# phase relative to the TB's clock, the TB might sample at the wrong time.
#
# But the TB uses @(posedge clk) for everything, and the TX changes on baud_tick
# (posedge clk). So the TB should see the TX output change at a posedge clk.
# The TB's recv_byte waits for data_o to go low using @(posedge clk).
# Once it detects the start bit, it waits 1.5 baud and samples.
#
# The key: when does data_o go low relative to the TB's recv_byte loop?
# The TX sets tx_out=0 in the IDLE state when start_req is set, on a baud_tick.
# The TB's recv_byte is polling data_o at every posedge clk.
# When the TB sees data_o=0, it starts counting.
#
# If the TX's baud_tick happens at a different cycle than the TB expects,
# the sampling could be off. But since both use the same clk and the TB
# uses BAUD_DIV=434 (same as baud_gen), the timing should align.
#
# Let me just add a debug to the TB to see what bytes it receives.

# Actually, let me check: maybe the issue is that the TB's recv_byte is catching
# the STOP bit of the previous TX as the START bit of the current TX.
# 
# The TX sends: start(0), 8 data bits, stop(1). 
# After the stop bit, tx_done fires and the TX goes to IDLE (tx_out=1).
# 
# If the TB's recv_byte is still running when the stop bit is sent, it might
# interpret the stop bit as idle and return. Then when the next TX starts,
# it catches the start bit correctly.
# 
# But if the TB's recv_byte returns DURING the stop bit, and the next TX starts
# before the TB's send_byte finishes... no, the TB sends the next pixel first.
#
# OK let me just add TB debug to see what's happening.

# Actually, let me look at the recv_byte more carefully.
# The recv_byte waits for data_o to go from 1 to 0 (start bit).
# Then waits HALF_BAUD + BAUD_DIV = 217 + 434 = 651 cycles.
# Then samples 8 bits at 434-cycle intervals.
# Then waits 434 cycles for stop bit.
#
# Total from start bit detection: 651 + 8*434 + 434 = 651 + 3472 + 434 = 4557 cycles
# = 10.5 baud periods.
#
# The TX sends: start(434) + 8*data(8*434) + stop(434) = 4340 cycles = 10 baud periods.
#
# So recv_byte takes 10.5 baud but TX takes 10 baud. The recv_byte finishes
# 0.5 baud after the TX finishes. That's fine.
#
# But the issue is the ALIGNMENT. When does the TB detect the start bit?
# The TX sets tx_out=0 on a baud_tick. The TB polls data_o at every posedge clk.
# The TB detects the start bit on the same posedge clk that the TX sets tx_out=0.
# Then the TB waits 651 cycles (1.5 baud) to sample the first data bit.
# The TX sets the first data bit on the NEXT baud_tick (434 cycles after start).
# So the TB samples at 651 cycles after start = 1.5 baud.
# The TX's first data bit starts at 1 baud and ends at 2 baud.
# The TB samples at 1.5 baud = middle of the first data bit. ✓
#
# This should work. But what if the TB detects the start bit LATE?
# If the TB is in a @(posedge clk) loop and the TX sets tx_out=0 on a posedge clk,
# the TB sees it on the SAME posedge clk (non-blocking assignment).
# Actually, in Verilog, the TB's while loop checks data_o after @(posedge clk).
# The TX's tx_out is set on @(posedge clk) with non-blocking assignment.
# So the TB sees the OLD value of tx_out on the same posedge clk, and the NEW
# value on the NEXT posedge clk.
#
# So the TB detects the start bit 1 cycle after the TX sets it.
# Then the TB waits 651 cycles. The TX's first data bit is at 434 cycles.
# The TB samples at 652 cycles = 1.501 baud. Still in the middle. ✓
#
# This 1-cycle delay is consistent for all bytes. It shouldn't cause an alternating
# pattern.
#
# I'm really stuck. Let me just add debug to the TB to see what it receives.

print("Adding TB debug")