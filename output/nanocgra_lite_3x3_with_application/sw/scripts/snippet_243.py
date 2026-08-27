# Let me think about this differently. The chip produces correct results for EVEN
# output indices and wrong results for ODD output indices. This is a very specific
# pattern. Let me look at the controller FSM timing more carefully.
#
# The TB sends pixels one at a time. After each send_byte, it calls recv_byte.
# For the first 66 pixels (row<2 or col<2), no result is produced, so recv_byte
# times out after 3*BAUD_DIV cycles. Then the TB sends the next pixel.
#
# For pixel 66 (row=2, col=2): result produced, controller goes S_TX_RESULT->S_NEXT.
# TB receives the result. Then sends pixel 67.
# For pixel 67 (row=2, col=3): result produced, controller goes S_TX_RESULT->S_NEXT.
# TB receives the result. Then sends pixel 68.
# ...and so on.
#
# So every pixel from 66 onward produces a result. The controller alternates:
# S_RECV (capture) -> S_TX_RESULT -> S_NEXT (wait tx_done) -> S_RECV (capture) -> ...
#
# Now, the key question: when does rx_valid fire relative to the controller state?
# The TB sends a byte (10 baud periods). rx_valid fires at the end of the byte.
# The controller should be in S_RECV at that point.
#
# But what if the controller is NOT in S_RECV? What if tx_done hasn't fired yet?
# Let me check the exact timing.
#
# After the controller captures a result (S_RECV -> S_TX_RESULT):
# Cycle 0: S_RECV, rx_valid=1, capture, pixel_cnt++, go to S_TX_RESULT
# Cycle 1: S_TX_RESULT, tx_start=1, go to S_NEXT
# Cycle 2: S_NEXT, wait for tx_done
# ... UART TX starts on next baud_tick after tx_start was latched
# ... UART TX takes 10 baud periods (start + 8 data + stop)
# ... tx_done fires at the end of the stop bit
# ... Controller goes back to S_RECV
#
# The TB's recv_byte:
# - Waits for data_o to go low (start bit of TX)
# - Samples 8 data bits at baud intervals
# - Waits for stop bit
# - Returns
# Total: ~10 baud periods
#
# After recv_byte returns, the TB immediately calls send_byte for the next pixel.
# send_byte takes 10 baud periods.
# 
# So the timeline is:
# t=0: controller captures result, starts TX
# t=0..10baud: TX in progress, TB receiving
# t=~10baud: TX done, tx_done fires, controller -> S_RECV
#            TB recv_byte returns (approximately same time)
# t=~10baud: TB starts send_byte for next pixel
# t=~20baud: send_byte done, rx_valid fires, controller in S_RECV captures
#
# This seems fine. But there might be an off-by-one in the baud timing.
# Let me check: does tx_done fire BEFORE or AFTER the TB's recv_byte returns?
#
# The UART TX: tx_done fires on the baud_tick in the STOP state.
# The STOP state is entered after the 8th data bit.
# So the sequence is: START(1 baud) + DATA(8 baud) + STOP(1 baud) = 10 baud.
# tx_done fires at the 10th baud_tick.
#
# The TB's recv_byte:
# - Detects start bit (data_o goes low)
# - Waits HALF_BAUD + BAUD_DIV = 1.5 baud to get to middle of first data bit
# - Samples 8 bits at BAUD_DIV intervals = 8 baud
# - Waits BAUD_DIV for stop bit = 1 baud
# Total after start bit detection: 1.5 + 8 + 1 = 10.5 baud
# But the start bit detection happens ~1 baud after TX starts.
# So recv_byte returns at ~11.5 baud after TX started.
# tx_done fires at ~10 baud after TX started.
# So tx_done fires ~1.5 baud BEFORE recv_byte returns. ✓
#
# Then the TB sends the next pixel (10 baud). By the time rx_valid fires (at ~21.5 baud),
# the controller has been in S_RECV since ~10 baud. ✓
#
# So the timing should be fine. The controller should capture every result.
# But the chip output shows odd indices are wrong. Let me check if maybe the
# controller is capturing the result one cycle too late or too early.
#
# Actually, wait. Let me re-read the controller code. The issue might be that
# the controller checks cur_col >= 2, but cur_col is the PRE-increment value.
# When pixel_cnt=66, cur_col=2. The controller captures the result. ✓
# When pixel_cnt=67, cur_col=3. The controller captures the result. ✓
# 
# But with my fix (continuous pixel acceptance), pixel_cnt increments on EVERY
# rx_valid, even in S_TX_RESULT/S_NEXT. So if a pixel arrives during S_NEXT,
# pixel_cnt increments but no result is captured. Then the next pixel arrives
# in S_RECV, and pixel_cnt has been incremented extra times.
#
# But I argued that pixels don't arrive during S_NEXT because the TB waits for
# recv_byte before sending the next pixel. Let me verify this by reverting my
# change and adding debug output instead.

# Actually, let me first revert the controller to the original and add debug.
print("Will revert controller and add debug")