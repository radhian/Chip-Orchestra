# The fix didn't work. Same mismatches. The issue is NOT pixel dropping.
# Let me reconsider. The pattern is: even indices match, odd indices don't.
# 
# Let me look at the window_3x3 more carefully. The look-ahead window:
# win = {sr0_1, sr0_2, lb0_data, sr1_1, sr1_2, lb1_data, sr2_1, sr2_2, pixel_in}
#
# After shift: sr0_2 <= lb0_data, sr0_1 <= sr0_2(old), sr0_0 <= sr0_1(old)
# So the new window columns are: (old sr0_1, old sr0_2, lb0_data) = cols (c-2, c-1, c)
# This is correct IF the shift registers are properly updated.
#
# But there's a TIMING issue. The win is combinational (look-ahead), computed from
# the CURRENT (pre-shift) register values. The sobel_core computes on this combinational win.
# The controller captures sobel_out when rx_valid && row>=2 && col>=2.
#
# At that moment, pixel_shift=1 (rx_valid), so the line buffers and window registers
# will update on this clock edge. The combinational win shows the POST-shift window.
# The controller captures sobel_out (which is based on the combinational win).
# This should be correct.
#
# BUT: the line buffers also update on this same edge. lb_rn1[col] <= pixel_in, 
# lb_rn2[col] <= lb_rn1_rd (old value). The window_3x3 reads lb0_data=lb_rn2_rd and 
# lb1_data=lb_rn1_rd which are the PRE-edge values (combinational read).
# So the window uses the old line buffer values, which is correct.
#
# Let me trace the actual values cycle by cycle. The issue might be in how
# the line buffers interact with the window on consecutive pixels.
#
# Actually, let me look at the golden functional model more carefully.
# In sobel_stream:
#   rn2 = lb_rn2[col] if row>=2 else 0
#   rn1 = lb_rn1[col] if row>=1 else 0
#   wcols[r] = wcols[r][1:] + [0]  # shift left
#   wcols[0][2] = rn2  # row N-2
#   wcols[1][2] = rn1  # row N-1
#   wcols[2][2] = px   # row N
#   if row>=1: lb_rn2[col] = lb_rn1[col]
#   lb_rn1[col] = px
#
# In the RTL:
#   lb_rn1_rd = mem[col] (pre-edge, row N-1)
#   lb_rn2_rd = mem[col] (pre-edge, row N-2)
#   win = {sr0_1, sr0_2, lb_rn2_rd, sr1_1, sr1_2, lb_rn1_rd, sr2_1, sr2_2, pixel_in}
#   On edge: sr0_2 <= lb_rn2_rd, sr1_2 <= lb_rn1_rd, sr2_2 <= pixel_in
#            lb_rn1[col] <= pixel_in, lb_rn2[col] <= lb_rn1_rd
#
# The golden model: wcols[0][2] = rn2 = lb_rn2[col] (before update)
# The RTL: sr0_2 <= lb_rn2_rd = lb_rn2[col] (before update) ✓
# The golden model: wcols[1][2] = rn1 = lb_rn1[col] (before update)
# The RTL: sr1_2 <= lb_rn1_rd = lb_rn1[col] (before update) ✓
# The golden model: wcols[2][2] = px
# The RTL: sr2_2 <= pixel_in ✓
#
# The golden model: lb_rn2[col] = lb_rn1[col] (old), then lb_rn1[col] = px
# The RTL: lb_rn2[col] <= lb_rn1_rd (old), lb_rn1[col] <= pixel_in ✓
#
# So the logic seems correct. But there's a subtle issue with the line buffer update.
# In the RTL, lb_rn2 writes lb_rn1_rd at col_cnt. But lb_rn1_rd is the combinational
# read of lb_rn1 at col_cnt (pre-edge). And lb_rn1 writes pixel_in at col_cnt.
# Both happen on the same edge. This is correct — lb_rn2 gets the old lb_rn1 value.
#
# Wait, but there's a problem with the line buffer update timing!
# The golden model updates lb_rn2[col] = lb_rn1[col] ONLY if row>=1.
# The RTL updates lb_rn2[col] <= lb_rn1_rd on EVERY pixel_shift, regardless of row.
# For row 0, lb_rn1[col] is 0 (reset), so lb_rn2[col] gets 0. That's fine.
# For row 1, lb_rn1[col] has the row-0 pixel, so lb_rn2[col] gets the row-0 pixel.
# But the golden model says: if row>=1: lb_rn2[col] = lb_rn1[col].
# So for row 0, the golden model does NOT update lb_rn2. The RTL does (with 0).
# This is the same since lb_rn1 is 0 at row 0. ✓
#
# Hmm, let me look at the golden model's line buffer tap condition:
#   rn2 = lb_rn2[col] if row>=2 else 0
#   rn1 = lb_rn1[col] if row>=1 else 0
# The RTL window_3x3 gets lb0_data=lb_rn2_rd and lb1_data=lb_rn1_rd unconditionally.
# But the top module passes lb_rn2_rd and lb_rn1_rd directly from the line buffers.
# There's NO row-based gating in the RTL!
#
# In the golden TopModel.step:
#   lb0_data = self.lb0.tap(col) if row>=2 else 0
#   lb1_data = self.lb1.tap(col) if row>=1 else 0
# 
# In the RTL top module:
#   lb_rn1_rd is directly from line_buffer (no gating)
#   lb_rn2_rd is directly from line_buffer (no gating)
#
# But this shouldn't matter for row>=2 (which is when results are produced).
# When row>=2, both row>=2 and row>=1 are true, so the gating doesn't change anything.
#
# Let me look at the ACTUAL window values. The issue is odd columns.
# Let me check if the line buffer read/write has a race condition.

# Actually, I think the issue might be simpler. Let me check the line_buffer write.
# The line_buffer writes at wr_col=col_cnt on pixel_shift. But col_cnt is the
# PRE-increment value. So when pixel_cnt=66 (col=2), it writes at col=2. ✓
# When pixel_cnt=67 (col=3), it writes at col=3. ✓
#
# But the line buffer read is at rd_col=col_cnt (same as wr_col). So it reads
# the value at the current column BEFORE the write. ✓
#
# Let me check: is there an issue with the line buffer for lb_rn2?
# lb_rn2 writes lb_rn1_rd at col_cnt. lb_rn1_rd is the pre-edge value of lb_rn1 at col_cnt.
# But lb_rn1 ALSO writes at col_cnt on the same edge. In Verilog, non-blocking assignments
# mean both use pre-edge values. So lb_rn2 gets the old lb_rn1 value. ✓
#
# Hmm, let me look at this from a different angle. Let me check if the window
# is correct for even columns but wrong for odd columns.
# 
# out[0] (col=2): chip=0x44, golden=0x44 ✓
# out[1] (col=3): chip=0x9c, golden=0x38 ✗
# out[2] (col=4): chip=0x3a, golden=0x3a ✓
# out[3] (col=5): chip=0x9e, golden=0x3c ✗
#
# So the window is correct for even columns but wrong for odd columns.
# This is a classic shift register issue — the shift is happening at the wrong time
# or the look-ahead is off by one for alternating columns.
#
# Wait — I bet the issue is that the controller goes to S_TX_RESULT after capturing
# a result, and during S_TX_RESULT/S_NEXT, it does NOT check for a new window.
# But with my fix, pixels are still accepted (pixel_shift=1). So the window shifts
# but no result is captured for that pixel.
#
# Let me check: after out[0] is captured (col=2), the controller goes to S_TX_RESULT.
# The next pixel (col=3) arrives. pixel_shift=1, so the window shifts. But the controller
# is in S_TX_RESULT or S_NEXT, so it does NOT capture the result.
# Then the controller goes back to S_RECV. The next pixel (col=4) arrives.
# pixel_shift=1, the window shifts, and the controller captures the result.
# But this is the result for col=4, not col=3!
#
# So out[1] in the chip is actually the result for col=4, not col=3!
# And out[2] is the result for col=5... wait, that doesn't match either.
#
# Actually, let me think again. The TB sends pixels one at a time with recv_byte in between.
# After sending pixel for col=2, the TB calls recv_byte. The controller captures the result
# and starts TX. The TB receives the result. Then the TB sends the next pixel (col=3).
# By this time, the controller should be back in S_RECV (tx_done fired during recv_byte).
# So the col=3 pixel arrives in S_RECV, and the controller captures the result.
# Then the TB receives that result, sends col=4, etc.
#
# So the controller should capture every result. The issue must be elsewhere.
# Let me check if the window is actually correct by looking at the timing more carefully.

# Actually, the problem might be that when the controller is in S_TX_RESULT (1 cycle),
# and rx_valid arrives at that exact cycle, the pixel is accepted (pixel_shift=1) but
# the controller doesn't check for a window. Then in S_NEXT, if another rx_valid arrives,
# same thing. The controller only checks in S_RECV.
#
# But the TB pacing should prevent this — the TB waits for recv_byte before sending
# the next pixel. The recv_byte takes ~10 baud periods. The controller's S_TX_RESULT
# is 1 cycle, S_NEXT waits for tx_done (which fires at the end of TX, ~10 baud periods).
# So by the time the TB sends the next pixel, the controller is in S_RECV.
#
# Unless... the TB's recv_byte returns BEFORE tx_done fires!
# Let me check: recv_byte samples the 8 data bits, then waits for the stop bit.
# After the stop bit wait, recv_byte returns. At that point, the UART TX is in the STOP
# state, and tx_done fires on the NEXT baud_tick. So there might be a race where
# recv_byte returns just before tx_done, and the TB sends the next pixel before the
# controller transitions from S_NEXT to S_RECV.

print("Need to check the exact timing of recv_byte return vs tx_done")