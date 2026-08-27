# Let me think about the synchronization more carefully.
# 
# The controller FSM:
# S_IDLE: wait for rx_valid -> S_RECV, accept pixel
# S_RECV: if rx_valid: accept pixel, if row>=2 && col>=2: capture result -> S_TX_RESULT
# S_TX_RESULT: tx_start=1, tx_data=result -> S_NEXT
# S_NEXT: if tx_done: out_cnt++, if all done -> S_IDLE, else -> S_RECV
# 
# Key: in S_RECV, the controller accepts rx_valid. In S_TX_RESULT and S_NEXT,
# it does NOT accept rx_valid. So if we send a pixel while the controller is
# in S_TX_RESULT/S_NEXT, the pixel is lost.
# 
# The controller is in S_RECV when:
# - It's the initial state (S_IDLE -> S_RECV on first pixel)
# - After tx_done in S_NEXT (S_NEXT -> S_RECV)
# 
# So the flow for a pixel that produces a result:
# 1. Controller in S_RECV, sees rx_valid, accepts pixel, goes to S_TX_RESULT
# 2. S_TX_RESULT: tx_start=1 -> S_NEXT
# 3. S_NEXT: waits for tx_done (4340 cycles for the TX frame)
# 4. tx_done -> S_RECV (ready for next pixel)
# 
# The TX frame takes 10 baud periods = 4340 cycles.
# During this time, the controller is in S_NEXT and won't accept new pixels.
# 
# So the TB must:
# 1. Send a pixel (4340 cycles for the UART frame)
# 2. If the pixel produces a result, wait for the TX frame to complete (4340 cycles)
# 3. Then send the next pixel
# 
# But how does the TB know if a pixel produces a result?
# - Pixels 0-65: no result (row<2 or col<2)
# - Pixels 66-1023: each produces a result (row>=2 and col>=2)
# 
# Wait, not exactly. The controller checks row>=2 and col>=2 AFTER
# accepting the pixel (using the NEW col/row after increment).
# Pixel 66: pixel_cnt goes from 66 to 67. col=67%32=3, row=67/32=2.
# row>=2 and col>=2 -> yes, result produced.
# 
# Pixel 65: pixel_cnt goes from 65 to 66. col=66%32=2, row=66/32=2.
# row>=2 and col>=2 -> yes! So pixel 65 (the 66th pixel, 0-indexed)
# produces the first result.
# 
# Actually, let me re-check. The controller in S_RECV:
# if rx_valid: _accept_pixel (pixel_cnt++, col=pixel_cnt%32, row=pixel_cnt/32)
# then if row>=2 and col>=2: capture result -> S_TX_RESULT
# 
# So after accepting pixel at index i (0-indexed):
# pixel_cnt = i+1, col = (i+1)%32, row = (i+1)/32
# 
# For i=65: pixel_cnt=66, col=66%32=2, row=66/32=2. row>=2 && col>=2 -> result!
# For i=64: pixel_cnt=65, col=65%32=1, row=65/32=2. col<2 -> no result.
# 
# So the first result is at pixel index 65 (the 66th pixel).
# After that, every pixel produces a result EXCEPT when the controller
# is in S_TX_RESULT/S_NEXT (it skips accepting pixels).
# 
# But wait — the controller goes S_RECV -> S_TX_RESULT -> S_NEXT -> S_RECV.
# In S_NEXT, it waits for tx_done. During this time, if we send another pixel,
# the UART RX produces rx_valid, but the controller ignores it.
# 
# So the controller effectively processes one pixel, sends a result,
# then processes the next pixel. The pixels that are sent during S_TX_RESULT/S_NEXT
# are LOST.
# 
# This means the TB CANNOT send all 1024 pixels back-to-back. It must
# synchronize: send a pixel, wait for the result TX to complete, then send
# the next pixel.
# 
# For the first 66 pixels (indices 0-64): no results, can send back-to-back.
# Wait, index 65 produces the first result. So indices 0-64 (65 pixels) can be
# sent back-to-back (no results to wait for).
# 
# Actually, indices 0-64: the controller is in S_RECV for all of them.
# It accepts each pixel and stays in S_RECV (no result). So we can send
# them back-to-back. But the UART RX needs time to process each byte
# (4340 cycles per byte). The controller sees rx_valid at the end of each
# UART frame and immediately accepts the pixel.
# 
# For index 65: the controller accepts the pixel, produces a result, goes
# to S_TX_RESULT -> S_NEXT. Now we need to wait for tx_done before sending
# the next pixel.
# 
# So the flow:
# 1. Send pixels 0-64 back-to-back (65 * 4340 = 282,100 cycles)
# 2. Send pixel 65, then wait for result TX (4340 + 4340 = 8680 cycles)
# 3. Send pixel 66, then wait for result TX
# 4. ... repeat for pixels 66-1023
# 
# But there's a subtlety: after sending pixel 65, the controller goes to
# S_TX_RESULT. The TX starts on the next baud tick. The TX frame takes
# 4340 cycles. During this time, the controller is in S_NEXT and won't
# accept new pixels. After tx_done, the controller goes to S_RECV.
# 
# The TB needs to:
# - After sending pixel 65, wait for the TX frame to complete
# - Capture the result byte from data_o
# - Then send pixel 66
# 
# The simplest approach: after each pixel that produces a result,
# wait for data_o to go from idle (1) to start (0) and back to idle (1).
# This takes ~4340 cycles.
# 
# But the TB also needs to capture the result byte. It can do this by
# sampling data_o at the baud rate during the TX frame.
# 
# Let me implement this with a UART receiver in the TB.

# Actually, let me think about whether we can send pixels 0-64 back-to-back.
# The UART RX takes 4340 cycles per byte. The controller sees rx_valid at
# the end of each frame. If we send the next byte immediately after the
# stop bit of the previous byte, the UART RX will see the start bit
# on the next baud tick. So the pixels are processed one per 4340 cycles.
# 
# But the controller in S_RECV accepts the pixel and stays in S_RECV
# (for pixels 0-64). So it's ready for the next rx_valid immediately.
# The next rx_valid comes 4340 cycles later (next UART frame).
# So yes, we can send pixels 0-64 back-to-back.
# 
# For pixel 65: the controller goes to S_TX_RESULT. The TX frame starts
# on the next baud tick. The TX takes 4340 cycles. During this time,
# the controller is in S_NEXT and won't accept new pixels.
# If we send pixel 66 immediately after pixel 65, the UART RX will
# produce rx_valid during the TX frame, but the controller ignores it.
# So pixel 66 is LOST.
# 
# Therefore, the TB must wait for the TX frame to complete before sending
# the next pixel. The TX frame takes 4340 cycles. The TB can detect the
# end of the TX frame by watching for data_o to return to idle (1) after
# the stop bit.
# 
# But there's a timing issue: the TX frame starts on the next baud tick
# after the controller enters S_TX_RESULT. The baud tick might not align
# with the end of the RX frame. So there might be a gap between the end
# of the RX frame and the start of the TX frame.
# 
# The approach:
# 1. Send a pixel via UART (drive data_i for 4340 cycles)
# 2. After the RX frame, wait for data_o to go low (TX start bit)
#    with a timeout of ~2 baud periods (868 cycles)
# 3. If data_o goes low, capture the TX frame (4340 cycles)
# 4. If data_o stays high (no result), proceed to the next pixel
# 
# But this is complex. Let me use a simpler approach:
# - Use a clock-based timeout: after sending a pixel, wait for a fixed
#   number of cycles for the result, then proceed.
# - The fixed wait should be enough for the TX frame (4340 cycles) plus
#   some margin.
# 
# Actually, the cleanest approach is to use the UART RX baud rate
# to receive bytes from data_o, and synchronize based on the number
# of results expected.
# 
# Let me implement the TB with:
# 1. A task to send a byte via UART on data_i
# 2. A task to receive a byte via UART from data_o
# 3. A main loop that sends pixels and receives results

# The send_byte task:
# - Drive start bit (0) for BAUD_DIV cycles
# - Drive 8 data bits LSB first, each for BAUD_DIV cycles
# - Drive stop bit (1) for BAUD_DIV cycles
# - Return to idle (1)

# The recv_byte task:
# - Wait for data_o to go low (start bit)
# - Wait BAUD_DIV/2 cycles to sample at the middle of each bit
# - Sample 8 data bits LSB first
# - Wait for stop bit
# - Return the received byte

# But the recv_byte task needs a timeout in case no result is produced.

# Let me implement this.

print("Main TB design:")
print("- send_byte task: serialize byte onto data_i at baud rate")
print("- recv_byte task: capture byte from data_o at baud rate (with timeout)")
print("- Main loop: send 1024 pixels, capture 900 results, compare against golden")