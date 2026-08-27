# Let me think about the timing more carefully.
# 
# The TB sends a byte via send_byte (takes 10 baud periods: start+8data+stop).
# Then calls recv_byte which waits for a start bit on data_o with timeout of 3 baud periods.
#
# The controller:
# - In S_RECV, on rx_valid: accepts pixel, pixel_cnt++, if row>=2&&col>=2: capture sobel_out, go S_TX_RESULT
# - S_TX_RESULT (1 cycle): tx_start=1, go S_NEXT
# - S_NEXT: wait for tx_done, then go S_RECV
#
# The uart_tx takes 10 baud periods to send a byte, then tx_done pulses.
#
# So after a result is captured, the controller is in S_NEXT for ~10 baud periods.
# During this time, the TB is in recv_byte receiving the result byte.
# After recv_byte returns, the TB immediately sends the next pixel.
#
# The next pixel takes 10 baud periods to send. During this time:
# - The controller should be back in S_RECV (tx_done happened)
# - The uart_rx receives the byte and pulses rx_valid
#
# The issue: when the controller captures sobel_out and goes to S_TX_RESULT,
# it does NOT accept the current pixel into the line buffer... wait, it DOES.
# pixel_shift = accept_pixel = (state==S_RECV) && rx_valid. 
# When state==S_RECV and rx_valid, pixel_shift=1, so the pixel IS shifted in.
# Then state goes to S_TX_RESULT. So the pixel is accepted.
#
# But here's the problem: the NEXT pixel (the one after the result-producing pixel)
# arrives while the controller is in S_TX_RESULT or S_NEXT. At that time, 
# accept_pixel=0 (state is not S_RECV), so pixel_shift=0, and the pixel is NOT accepted!
# The uart_rx still receives the byte and pulses rx_valid, but the controller ignores it.
#
# So the controller DROPS every other pixel when it's producing results!
# 
# When row>=2 and col>=2, every pixel produces a result. The controller goes:
# S_RECV (accept pixel N, produce result) -> S_TX_RESULT -> S_NEXT (wait tx_done) -> S_RECV
# During S_TX_RESULT + S_NEXT, pixel N+1 arrives and is DROPPED.
# Then in S_RECV, pixel N+2 arrives and is accepted.
#
# So the controller only accepts every OTHER pixel once results start!
# This means:
# - out[0] uses pixel at col=2 (accepted)
# - pixel at col=3 is DROPPED
# - out[1] uses pixel at col=4 (accepted) but the window is wrong because col=3 was dropped
#
# This explains the odd/even pattern! Even output indices (0,2,4...) use correctly-shifted
# windows, odd output indices (1,3,5...) use windows where a pixel was dropped.

# But wait — the golden functional model (sobel_stream) accepts ALL pixels.
# The golden controller model also drops pixels (same FSM). But the TB uses sobel_stream
# (the functional model) to generate golden_output.mem, NOT the cycle-accurate model.

# So the fix must be in the RTL controller: it needs to accept ALL pixels, even during TX.
# The golden functional model accepts every pixel continuously.

# The real fix: the controller should NOT block pixel acceptance during TX.
# It should accept pixels in S_TX_RESULT and S_NEXT too (or use a different approach).

# Actually, looking at the golden controller more carefully:
# In S_RECV, on rx_valid: _accept_pixel, then if row>=2&&col>=2: capture, go S_TX_RESULT
# In S_TX_RESULT: tx_start=1, go S_NEXT  
# In S_NEXT: if tx_done: out_cnt++, go S_RECV or S_IDLE
# 
# The golden controller ALSO doesn't accept pixels in S_TX_RESULT/S_NEXT!
# But the functional model (sobel_stream) does. The TB uses the functional model.
# 
# So the RTL matches the golden controller, but the TB's golden reference is the 
# functional model which accepts all pixels. This is the mismatch.
#
# The fix: make the RTL controller accept pixels even during TX states.
# OR: the TB should pace pixel sending to match the controller's ability to process.
#
# Actually, the TB sends pixels one at a time with recv_byte in between.
# The issue is that after a result is produced, the controller is busy with TX
# and the TB sends the next pixel which gets dropped.
#
# The cleanest fix: make the controller accept pixels in ALL states (not just S_RECV).
# This matches the functional model's continuous streaming.

print("The fix: controller should accept pixels continuously, not just in S_RECV")
print("This matches the golden functional model sobel_stream which accepts all pixels")