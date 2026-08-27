# Everything matches. The bug is in the RTL streaming datapath.
# Let me add debug $display to the testbench to see what window the chip computes.
# Actually, let me add a debug output directly in the top module temporarily.
# 
# Better: let me think about the timing issue with the controller FSM and TB.
#
# The TB sends a byte (10 baud periods), then calls recv_byte.
# recv_byte waits for data_o to go low (start bit) with timeout of 3*BAUD_DIV cycles.
# If no result is produced, it times out after 3 baud periods and the TB sends the next pixel.
# If a result IS produced, it receives the byte (10 baud periods).
#
# The key question: when the controller captures a result and goes to S_TX_RESULT,
# does the TB's recv_byte see the result? And does the next pixel arrive in S_RECV?
#
# Let me trace the timing for the first result (col=2, row=2, pixel_cnt=66):
# 1. TB sends pixel 66 (10 baud periods). At the end, rx_valid pulses.
# 2. Controller in S_RECV: pixel_shift=1, pixel_cnt=66->67, captures sobel_out, goes to S_TX_RESULT.
# 3. Controller in S_TX_RESULT (1 cycle): tx_start=1, goes to S_NEXT.
# 4. Controller in S_NEXT: waits for tx_done.
# 5. UART TX starts sending the result byte (10 baud periods).
# 6. TB calls recv_byte, sees start bit, receives the byte (10 baud periods).
# 7. After recv_byte returns, TB sends pixel 67 (col=3).
# 8. Pixel 67 takes 10 baud periods to send. At the end, rx_valid pulses.
# 9. By this time, tx_done has fired (at the end of TX, ~step 5+10 baud).
#    The controller transitioned from S_NEXT to S_RECV.
# 10. Controller in S_RECV: pixel_shift=1, pixel_cnt=67->68, captures sobel_out for col=3.
#
# This seems correct. But there's a subtlety: the UART TX might not start immediately.
# The tx_start is asserted in S_TX_RESULT (1 cycle). The UART TX latches it and starts
# on the next baud_tick. So there might be a delay of up to 1 baud period before TX starts.
# During this delay, the TB's recv_byte is waiting for the start bit.
# The timeout is 3*BAUD_DIV = 3 baud periods. So it should catch it.
#
# But what if the TB sends the next pixel BEFORE the controller is back in S_RECV?
# After recv_byte returns, the TB immediately sends the next pixel.
# recv_byte returns after sampling 8 data bits + waiting for stop bit = 9 baud periods
# after the start bit. The TX takes 10 baud periods total (start + 8 data + stop).
# tx_done fires at the end of the stop bit (10th baud period).
# So recv_byte returns at ~9 baud periods, and tx_done fires at ~10 baud periods.
# There's a 1 baud period gap where the TB has started sending the next pixel
# but the controller is still in S_NEXT (tx_done hasn't fired yet).
#
# The next pixel takes 10 baud periods to send. The first bit (start bit) takes
# 1 baud period. During this time, tx_done fires and the controller goes to S_RECV.
# So by the time rx_valid pulses (at the end of the byte, 10 baud periods later),
# the controller is in S_RECV. ✓
#
# So the timing should be fine. The issue must be in the datapath itself.
# Let me add debug output to see the actual window values.

# Let me check: maybe the issue is that the line buffer read is wrong.
# The line_buffer reads at rd_col=col_cnt. But col_cnt is pixel_cnt[4:0].
# When pixel_cnt=66, col_cnt=66%32=2. The line buffer reads mem[2].
# But mem[2] was written when col_cnt was 2 in a PREVIOUS row.
# For row 2, col 2: lb_rn1[2] should have the row-1 pixel at col 2.
# lb_rn1[2] was written when pixel_cnt=34 (row=1, col=2) with pixel_in=pixels[34].
# pixels[34] = row 1, col 2 = 167. Let me verify.

IMG_W = 32
print("pixels[34] (row1,col2):", pixels[34])  # should be 167
print("pixels[2] (row0,col2):", pixels[2])    # should be 155
print("pixels[66] (row2,col2):", pixels[66])  # should be 169

# golden out[0] window: rows 0,1,2 cols 0,1,2 = [151,155,155, 165,167,167, 167,169,169]
# So at col=2, row=2: the window is cols 0,1,2 of rows 0,1,2.
# lb_rn2[0] = row0 col0 = 151, lb_rn2[1] = row0 col1 = 155, lb_rn2[2] = row0 col2 = 155
# lb_rn1[0] = row1 col0 = 165, lb_rn1[1] = row1 col1 = 167, lb_rn1[2] = row1 col2 = 167
# pixel_in = row2 col2 = 169
# 
# But the window uses shift registers for cols 0,1 and line buffer for col 2.
# sr0_1 = col0 of row N-2, sr0_2 = col1 of row N-2, lb0_data = col2 of row N-2
# sr1_1 = col0 of row N-1, sr1_2 = col1 of row N-1, lb1_data = col1 of row N-1
# sr2_1 = col0 of row N, sr2_2 = col1 of row N, pixel_in = col2 of row N
#
# For this to work, when we process col=2:
# sr0_1 should hold row N-2 col 0 = 151
# sr0_2 should hold row N-2 col 1 = 155
# lb0_data = lb_rn2[2] = row N-2 col 2 = 155
# 
# sr0_1 was set when we processed col=0: sr0_2 <= lb0_data = lb_rn2[0] = 151
# Then when we processed col=1: sr0_1 <= sr0_2 = 151, sr0_2 <= lb0_data = lb_rn2[1] = 155
# Then when we process col=2: sr0_1 = 151, sr0_2 = 155, lb0_data = lb_rn2[2] = 155 ✓
#
# This is correct for col=2. Let me check col=3.
# For col=3: sr0_1 = col1 = 155, sr0_2 = col2 = 155, lb0_data = lb_rn2[3] = row0 col3 = 155
# Window row N-2: [155, 155, 155] ✓ (golden has [155,155,155] for out[1])
# 
# sr1_1 = col1 of row N-1 = 167, sr1_2 = col2 of row N-1 = 167, lb1_data = lb_rn1[3] = 167
# Window row N-1: [167, 167, 167] ✓
#
# sr2_1 = col1 of row N = 167, sr2_2 = col2 of row N = 169, pixel_in = col3 of row N = 169
# Window row N: [167, 169, 169]
# But golden has [169, 169, 169] for out[1]!
# 
# AH HA! The golden window for out[1] is [155,155,155, 167,167,167, 169,169,169]
# But the RTL would give [155,155,155, 167,167,167, 167,169,169]
# 
# The difference is in row N (current row): golden has [169,169,169] but RTL has [167,169,169].
# sr2_1 = 167 but should be 169!
#
# sr2 is the shift register for the current row (row N = pixel_in).
# When col=0: sr2_2 <= pixel_in = pixels[row*32+0]
# When col=1: sr2_1 <= sr2_2 = pixels[row*32+0], sr2_2 <= pixel_in = pixels[row*32+1]
# When col=2: sr2_1 <= sr2_2 = pixels[row*32+1], sr2_2 <= pixel_in = pixels[row*32+2]
# When col=3: sr2_1 = pixels[row*32+1], sr2_2 = pixels[row*32+2], pixel_in = pixels[row*32+3]
#
# For row=2: pixels[2*32+1]=pixels[65]=167, pixels[2*32+2]=pixels[66]=169, pixels[2*32+3]=pixels[67]=169
# So sr2_1=167, sr2_2=169, pixel_in=169 → row N = [167, 169, 169]
# But golden has [169, 169, 169]!
#
# The golden model: wcols[2] = [col c-2, col c-1, col c] of row N
# For col=3: wcols[2] = [pixels[2*32+1], pixels[2*32+2], pixels[2*32+3]] = [167, 169, 169]
# Wait, that's the same as the RTL! Let me re-check the golden.

# golden out[1] window from my earlier trace:
# out[1] idx=67 center=(2,3) win=[155, 155, 155, 167, 167, 167, 169, 169, 169] out=0x38
# 
# But the golden streaming model uses wcols[2] = [col c-2, col c-1, col c] of row N (pixel_in)
# For idx=67 (row=2, col=3): wcols[2] should be [pixels[64], pixels[65], pixels[66]]
# Wait no — the streaming model processes pixels sequentially. When it processes idx=67,
# pixel_in = pixels[67]. The wcols[2] shift register has been accumulating:
# At idx=64 (col=0): wcols[2] = [0, 0, pixels[64]]
# At idx=65 (col=1): wcols[2] = [0, pixels[64], pixels[65]]
# At idx=66 (col=2): wcols[2] = [pixels[64], pixels[65], pixels[66]]
# At idx=67 (col=3): wcols[2] = [pixels[65], pixels[66], pixels[67]]
# 
# pixels[64]=167, pixels[65]=167, pixels[66]=169, pixels[67]=169
# So wcols[2] at idx=67 = [167, 169, 169]
# But the golden trace says [169, 169, 169]!
# 
# Wait, let me re-check. The golden trace I ran earlier showed:
# out[1] idx=67 center=(2,3) win=[155, 155, 155, 167, 167, 167, 169, 169, 169]
# 
# But that can't be right if wcols[2] = [pixels[65], pixels[66], pixels[67]] = [167, 169, 169]
# 
# Let me re-run the trace more carefully.

print("pixels[64..67]:", pixels[64:68])