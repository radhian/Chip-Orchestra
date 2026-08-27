# Let me think about the synchronization more carefully.
# 
# The key issue: the controller blocks on tx_done before accepting the next pixel.
# So the TB must wait for the TX frame to complete before sending the next pixel.
# 
# But for the first 65 pixels (indices 0-64), no results are produced.
# The controller stays in S_RECV and accepts each pixel immediately.
# So the TB can send these back-to-back.
# 
# For pixel 65 onwards, each pixel produces a result. The controller goes
# to S_TX_RESULT -> S_NEXT, and the TB must wait for tx_done.
# 
# But there's a subtlety: the UART RX and TX share the same baud_gen
# (each has its own baud_gen instance). The RX baud_gen and TX baud_gen
# run independently. The RX sees the start bit at its baud tick, and
# the TX starts at its baud tick.
# 
# The flow for pixel 65:
# 1. TB sends pixel 65 via UART on data_i (4340 cycles)
# 2. UART RX detects start bit at its baud tick, samples 8 bits, produces rx_valid
# 3. Controller sees rx_valid, accepts pixel 65, detects row>=2 && col>=2
# 4. Controller goes to S_TX_RESULT, asserts tx_start with result
# 5. UART TX latches tx_start, waits for its baud tick
# 6. UART TX sends the frame (4340 cycles)
# 7. tx_done pulses at the end of the TX frame
# 8. Controller goes to S_RECV
# 9. TB sends pixel 66
# 
# The total time for pixel 65: 4340 (RX) + 4340 (TX) = 8680 cycles.
# But there might be a gap between RX completion and TX start (waiting for baud tick).
# 
# The TB approach:
# 1. Send pixel via UART (4340 cycles)
# 2. After sending, wait for data_o to go low (TX start bit) with timeout
# 3. If data_o goes low, receive the TX frame (4340 cycles)
# 4. If timeout, no result, proceed to next pixel
# 
# But the timeout needs to be long enough to account for the gap between
# RX completion and TX start. The gap is at most 434 cycles (one baud period).
# 
# Actually, let me think about this differently. The controller enters
# S_TX_RESULT immediately after accepting the pixel (on rx_valid).
# In S_TX_RESULT, it asserts tx_start. The UART TX latches tx_start
# on the next clock (not baud tick). Then on the next baud tick, the TX
# starts the frame (start bit on data_o).
# 
# So the gap between rx_valid and the TX start bit is at most 434 cycles
# (waiting for the next baud tick). The TB should wait at least 434 cycles
# after sending the pixel before checking for a TX start bit.
# 
# But the TB also needs to wait for the RX to complete. The RX completes
# at the baud tick after the 8th data bit. The TB sends the stop bit
# and then checks for the TX start bit.
# 
# Let me simplify: after sending a pixel, wait for up to 2 baud periods
# (868 cycles) for data_o to go low. If it does, receive the TX frame.
# If not, proceed to the next pixel.
# 
# For the first 65 pixels: no TX, so the timeout will expire and we proceed.
# For pixel 65 onwards: TX starts within 1 baud period, so we catch it.
# 
# But this adds 868 cycles of overhead per pixel for the first 65 pixels.
# 65 * 868 = 56,420 cycles. Not significant.
# 
# Actually, for the first 65 pixels, we can skip the wait entirely
# since we know no results are produced. Let me optimize:
# - Pixels 0-64: send back-to-back, no wait
# - Pixels 65-1023: send, wait for result, receive result
# 
# But the controller might miss some pixels if we send them too fast
# during the first 65. Let me check: the controller in S_RECV accepts
# rx_valid. The UART RX produces rx_valid at the end of each frame.
# If we send the next frame immediately after the stop bit, the UART RX
# will see the start bit on the next baud tick. So the controller sees
# rx_valid every 4340 cycles. It accepts each pixel and stays in S_RECV.
# This should work.
# 
# But there's a subtlety: the UART RX's prev_line tracking. After the
# stop bit (1), the RX is in STOP state, waiting for a falling edge
# (prev_line=1, rx_in=0). If we send the start bit (0) immediately after
# the stop bit, the RX will see the falling edge on the next baud tick.
# This should work.
# 
# Let me implement the TB.

# Actually, I realize there's a much simpler approach. Instead of trying
# to synchronize precisely, I can:
# 1. Send ALL 1024 pixels with enough spacing between them to allow
#    the controller to process and send results.
# 2. Use a separate always block to capture bytes from data_o.
# 3. After all pixels are sent, wait for remaining results.
# 4. Compare captured results against golden.
# 
# The spacing: each pixel needs 4340 cycles (RX) + 4340 cycles (TX) = 8680 cycles.
# For pixels without results: 4340 cycles.
# 
# But the controller blocks during TX, so if we send the next pixel during TX,
# it's lost. So we need to wait for TX to complete.
# 
# The simplest approach: send a pixel, then wait for a fixed time (2 baud periods
# = 868 cycles) for a TX start bit. If detected, receive the TX frame. Then
# send the next pixel.
# 
# Let me implement this with a state machine in the TB.

# Actually, let me use a much simpler approach that avoids the synchronization issue:
# 
# 1. Send a pixel via UART
# 2. After the stop bit, wait for data_o to go low (TX start bit)
# 3. If data_o goes low within a timeout, receive the TX frame
# 4. Repeat
# 
# The timeout: 2 * BAUD_DIV cycles (enough for the TX to start)
# 
# For pixels without results: the timeout expires, we proceed.
# For pixels with results: we catch the TX start bit and receive the frame.
# 
# This is clean and simple. Let me implement it.

# One more thing: the result registers need to be sized for the full value range.
# The golden output has values 0..255, so we need reg [7:0] for each result.
# 900 results = 30*30.

print("Implementation plan:")
print("- 900 result registers: reg [7:0] chip_out [0:899]")
print("- send_byte task: 10 bits * BAUD_DIV cycles each")
print("- recv_result: wait for data_o falling edge, sample 8 bits")
print("- Main loop: send 1024 pixels, capture results")
print("- Compare: $writememh to waves/chip_output.mem, then compare against golden")