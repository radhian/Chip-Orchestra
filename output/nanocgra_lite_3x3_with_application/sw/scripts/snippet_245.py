# The debug shows the CORRECT window and sobel values!
# DBG out[1] row=2 col=3 win=a9 a9 a9 a7 a7 a7 9b 9b 9b sobel=38
# That's 0x38 = 56, which matches golden!
# 
# But the chip output is 0x9c = 156 for index 1.
# So the sobel_core computes the RIGHT value (0x38), but the chip OUTPUTS 0x9c!
# 
# The problem is in the TX path — the controller captures sobel_out, but something
# goes wrong during transmission or capture.
#
# Let me check: the controller captures sobel_out into result_reg when rx_valid
# && row>=2 && col>=2 in S_RECV. Then in S_TX_RESULT, it sends result_reg via TX.
#
# But wait — the debug shows sobel=0x38 at the capture point. The controller
# should capture 0x38 into result_reg. But the chip outputs 0x9c.
#
# 0x9c = 156. 0x38 = 56. 156 - 56 = 100. 
# 0x9c in binary = 10011100. 0x38 = 00111000.
# 
# Hmm, what if the TX is sending the wrong byte? Or what if the TB is receiving
# the wrong byte? Or what if the controller captures the wrong value?
#
# Let me add more debug: show what result_reg and tx_data are.

# Actually, let me check: the debug condition is rx_valid && row>=2 && col>=2.
# But the controller only captures in S_RECV. If the controller is NOT in S_RECV
# when rx_valid fires (e.g., it's in S_NEXT), the debug shows the sobel value
# but the controller doesn't capture it.
#
# The debug shows 12 captures (out[0]..out[11]), all with correct sobel values.
# But the chip output has wrong values for odd indices.
#
# So the issue is: the controller captures the right sobel_out, but the TX sends
# the wrong byte, OR the TB receives the wrong byte.
#
# Let me check: maybe the controller captures sobel_out for even indices but
# NOT for odd indices (because it's in S_NEXT when the odd pixel arrives).
# Then the TB receives a stale or wrong byte for odd indices.
#
# Let me trace: 
# out[0] (col=2): controller in S_RECV, captures 0x44, goes to S_TX_RESULT->S_NEXT
# TB receives 0x44. ✓
# Then TB sends pixel for col=3.
# If the controller is still in S_NEXT when col=3's rx_valid fires, it doesn't capture.
# The TB then calls recv_byte, which times out (no result). 
# Then TB sends pixel for col=4.
# Controller is now in S_RECV, captures 0x3a (for col=4, not col=3!).
# TB receives 0x3a. This becomes chip_out[1] = 0x3a. But the actual chip_out[1] = 0x9c!
#
# Wait, that doesn't match either. Let me think again.
# 
# Actually, the TB captures results in order. If the controller misses col=3's result,
# then chip_out[1] would be the result for col=4 (0x3a), not 0x9c.
# But chip_out[1] = 0x9c, which is NOT any of the correct sobel values.
#
# So something else is going on. Let me check if the TB is receiving garbage bytes
# from the UART TX. Maybe the TX is sending a byte at the wrong time, and the TB
# interprets a partial byte as a result.
#
# 0x9c = 10011100. What if the TB is sampling the UART line at the wrong time
# and getting garbage?
#
# Actually, let me check: maybe the controller IS capturing for odd indices,
# but it captures the WRONG value. The debug shows the correct sobel value
# at the capture point, but maybe the controller captures a different value.
#
# The debug condition (rx_valid && row>=2 && col>=2) fires for EVERY pixel,
# but the controller only captures in S_RECV. So the debug might show captures
# that the controller doesn't actually make.
#
# Let me add debug to show the controller state at each rx_valid.

print("Need to add controller state debug")