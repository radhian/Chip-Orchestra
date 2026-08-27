# The controller captures EVERY result correctly! Every rx_valid produces a tx_start
# with the correct sobel value. So the controller is NOT dropping any results.
# 
# tx_data values: 44, 38, 3a, 3c, 3e, 3c, 3e, 3c, 3c, 3a, 3c, 3c, 3c, 3a, 3a, 3c, 3c, 3a, 3e, 3e
# These are ALL correct! They match the golden output.
# 
# But the chip output is: 44, 9c, 3a, 9e, 3e, 9e, 3e, 9e, 3c, 9d, 3c, 9e
# 
# So the TX sends the right byte, but the TB receives the wrong byte for odd indices!
# The issue is in the UART TX/RX timing — the TB is sampling at the wrong time
# and getting garbage for every other byte.
#
# 0x9c = 10011100. The correct value is 0x38 = 00111000.
# 0x9e = 10011110. The correct value is 0x3c = 00111100.
# 
# 0x9c = 10011100
# 0x38 = 00111000
# XOR = 10110100
# 
# 0x9e = 10011110
# 0x3c = 00111100
# XOR = 10100010
# 
# Hmm, no obvious bit pattern. Let me check if the TB is off by one bit period.
# 
# Actually, the issue might be that the TB's recv_byte is not properly synchronized
# with the TX. After send_byte returns, the TB immediately calls recv_byte.
# But the controller might start TX at a different time than expected.
#
# Let me look at the timing more carefully. The send_byte takes 10 baud periods.
# At the end, the stop bit is high for 1 baud period. Then the TB calls recv_byte.
# recv_byte waits for data_o to go low (start bit of TX).
#
# But the controller captures the result on rx_valid (which fires at the END of
# the received byte, during the stop bit). Then it goes to S_TX_RESULT (1 cycle),
# then S_NEXT. The TX starts on the next baud_tick after tx_start is latched.
#
# The issue: the TB's recv_byte has a timeout of 3*BAUD_DIV. If the TX doesn't
# start within 3 baud periods, recv_byte times out and returns ok=0.
# Then the TB sends the next pixel. But the TX might start later!
#
# If the TX starts AFTER the timeout, the TB has already started sending the next
# pixel. The TX output (data_o) goes low (start bit) while the TB is sending.
# The TB's send_byte drives data_i, not data_o. So the TX start bit on data_o
# is missed by recv_byte (which already timed out).
#
# Then when the TB calls recv_byte again after the next send_byte, it might catch
# the MIDDLE of the ongoing TX, receiving garbage.
#
# This would explain the alternating pattern: 
# - Even indices: TX starts in time, recv_byte catches it correctly.
# - Odd indices: TX starts too late, recv_byte times out, then catches garbage
#   on the next attempt.
#
# But wait, the debug shows tx_start fires for EVERY result. And the controller
# is fast (1 cycle from capture to tx_start). The TX should start within 1 baud
# period. The timeout is 3 baud periods. So it should catch it.
#
# Unless the issue is that the TX is STILL SENDING the previous byte when the
# new tx_start arrives! The uart_tx latches tx_start, but if it's still sending,
# the new byte queues up. But the TB's recv_byte might catch the tail of the
# previous TX and the head of the new TX, getting garbage.
#
# Let me check: does the TX finish before the next tx_start?
# The TX takes 10 baud periods. The TB sends a pixel (10 baud), then recv_byte
# (10 baud). So there's 20 baud between tx_start events. The TX takes 10 baud.
# So the TX should finish well before the next tx_start. ✓
#
# Hmm, but what about the FIRST result? The first 66 pixels don't produce results.
# The TB sends each pixel and calls recv_byte, which times out after 3 baud periods.
# So the TB sends pixels at intervals of ~13 baud periods (10 for send + 3 for timeout).
# 
# When the first result is produced (pixel 66), the controller captures and starts TX.
# The TB calls recv_byte. The TX starts within ~1 baud period. recv_byte catches it.
# The TB receives the byte (10 baud). Then sends the next pixel (10 baud).
# 
# For the next result (pixel 67), the controller captures and starts TX.
# But wait — does the controller capture pixel 67's result?
# The debug shows it does! tx_start fires with tx_data=0x38 for pixel 67.
# 
# So the TX sends 0x38, but the TB receives 0x9c. The issue is in the UART
# TX-to-TB-receive timing.
#
# Let me check: maybe the TB's recv_byte is sampling at the wrong time because
# the baud rates don't match exactly. The baud_gen produces a tick every 434
# cycles. The TB uses BAUD_DIV=434 for bit timing. If there's a slight mismatch,
# the sampling could drift.
#
# Actually, let me check the baud_gen.

print("Need to check baud_gen.v")