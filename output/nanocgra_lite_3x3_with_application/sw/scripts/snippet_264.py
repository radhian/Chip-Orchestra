# The baud_gen reset didn't help. The issue is more subtle.
# Let me think about this more carefully.
#
# The baud_gen reset happens on the baud_tick when IDLE->START transitions.
# But at that point, baud_cnt is already at 0 (because the tick just fired
# when baud_cnt was at BAUD_DIV-1, and the reset code sets it to 0).
# So resetting baud_cnt to 0 at that point doesn't change anything -
# it would be 0 anyway.
#
# The real issue: the start bit (tx_out=0) is set on a baud_tick.
# The baud_tick happens when baud_cnt reaches BAUD_DIV-1.
# The start bit lasts until the next baud_tick (434 cycles).
# Then bit 0 is set, etc.
#
# The tb's recv_byte detects the start bit 1 cycle after the baud_tick
# (on the next posedge). Then it waits HALF_BAUD + BAUD_DIV = 651 cycles.
# This puts the first sample at 652 cycles after the baud_tick.
# Bit 0 starts at 434 cycles after the start bit's baud_tick.
# So the first sample is at 652 - 434 = 218 cycles into bit 0. Good.
#
# But the issue is that the tb's cycle counting and the baud_gen's
# cycle counting drift apart over time.
#
# Let me trace the EXACT timing:
# 
# The baud_gen counts: 0, 1, 2, ..., 433, [tick], 0, 1, 2, ..., 433, [tick], ...
# The tick happens when cnt goes from 433 to 0.
#
# The tb's recv_byte:
# - Detects start bit at posedge clk (1 cycle after tx_out changes)
# - tx_out changes on the posedge when baud_tick=1 (baud_cnt was 433, now 0)
# - So the tb detects the start bit on the posedge when baud_cnt=1 (1 cycle after tick)
# - Wait, let me be more precise:
#   - At posedge with baud_cnt=433: baud_tick becomes 1 (for NEXT cycle)
#   - Actually, baud_tick is registered. Let me re-read the baud_gen:
#     if (cnt == BAUD_DIV-1): cnt<=0, baud_tick<=1
#     else: cnt<=cnt+1, baud_tick<=0
#   - So baud_tick=1 on the cycle AFTER cnt=433. Wait no:
#     At posedge when cnt=433: cnt becomes 0, baud_tick becomes 1.
#     These take effect AFTER the posedge. So on the NEXT posedge,
#     baud_tick is 1 and cnt is 0.
#   - The UART TX sees baud_tick=1 on this posedge and changes tx_out.
#   - The tb sees the new tx_out on the SAME posedge (because tx_out
#     is a reg that changes on this posedge, and the tb samples data_o
#     which is tx_out).
#
# Wait, there's a subtlety. In Verilog, all always blocks trigger on
# the same posedge. The baud_gen sets baud_tick=1 (takes effect after
# the edge). The UART TX checks baud_tick in its always block. But
# baud_tick is a reg, so the UART TX sees the OLD value of baud_tick
# (before the edge), not the new value.
#
# Actually, let me re-read the baud_gen:
#   always @(posedge clk or negedge rst_n) begin
#     if (cnt == BAUD_DIV - 1) begin
#       cnt <= 0;
#       baud_tick <= 1;
#     end else begin
#       cnt <= cnt + 1;
#       baud_tick <= 0;
#     end
#   end
#
# And the UART TX:
#   always @(posedge clk or negedge rst_n) begin
#     ...
#     if (baud_tick) begin
#       case (state)
#         IDLE: if (start_req) begin tx_out <= 0; ... end
#         ...
#       endcase
#     end
#   end
#
# In Verilog, when both always blocks trigger on the same posedge:
# - baud_gen evaluates: if cnt==433, sets baud_tick<=1 (NBA, takes effect after)
# - UART TX evaluates: checks baud_tick (OLD value, before this edge)
#
# So the UART TX sees baud_tick=1 on the posedge AFTER baud_gen sets it.
# That is:
# - Cycle N: baud_gen has cnt=433. Sets baud_tick<=1, cnt<=0.
# - Cycle N+1: baud_tick is now 1. UART TX sees baud_tick=1, changes tx_out.
#   baud_gen has cnt=0, sets baud_tick<=0, cnt<=1.
# - Cycle N+2: baud_tick is 0. tx_out has the new value.
#   The tb samples data_o on this posedge and sees the new tx_out.
#
# Wait, the UART TX changes tx_out on cycle N+1 (when it sees baud_tick=1).
# tx_out is a reg, so the new value takes effect after cycle N+1's posedge.
# The tb samples data_o on cycle N+2's posedge and sees the new tx_out.
#
# So the tb detects the start bit 2 cycles after the baud_gen's cnt wraps.
# 
# Let me define t=0 as the cycle when the tb detects the start bit.
# At t=0: tb sees data_o=0 (start bit). baud_cnt is now 2 (it was 0 at
# cycle N+1, 1 at cycle N+2, 2 at cycle N+3=t).
# Wait, I'm getting confused. Let me use absolute cycle numbers.
#
# Cycle 0: baud_cnt=433. baud_gen sets baud_cnt<=0, baud_tick<=1.
# Cycle 1: baud_cnt=0, baud_tick=1. UART TX sees baud_tick=1, sets tx_out<=0.
#          baud_gen sets baud_cnt<=1, baud_tick<=0.
# Cycle 2: baud_cnt=1, baud_tick=0. tx_out is now 0 (start bit visible).
#          The tb samples data_o=0 on this posedge. START BIT DETECTED at t=0.
#          baud_gen sets baud_cnt<=2, baud_tick<=0.
# Cycle 3 (t=1): baud_cnt=2. tb waits (HALF_BAUD+BAUD_DIV = 651 cycles).
# ...
# Cycle 2+651=653 (t=651): tb samples first data bit.
#   baud_cnt at this cycle: (2 + 651) mod 434 = 653 mod 434 = 219.
#   The next baud_tick after cycle 1 is at cycle 1+434=435.
#   Then 435+434=869, 869+434=1303, ...
#   At cycle 435: baud_tick=1, UART TX sets tx_out to bit 0.
#   At cycle 436: tx_out = bit 0 is visible.
#   At cycle 653 (t=651): tb samples. baud_cnt=219.
#   Bit 0 is visible from cycle 436 to cycle 869 (next baud_tick at 869).
#   653 is in [436, 869]. So the tb samples bit 0 correctly. ✓
#
# Then the tb samples every 434 cycles:
#   t=651 (cycle 653): bit 0 ✓
#   t=1085 (cycle 1087): bit 1? 
#     Bit 1 is visible from cycle 870 to cycle 1303.
#     1087 is in [870, 1303]. ✓
#   t=1519 (cycle 1521): bit 2?
#     Bit 2 is visible from cycle 1304 to cycle 1737.
#     1521 is in [1304, 1737]. ✓
#   ...
#   t=3689 (cycle 3691): bit 7?
#     Bit 7 is visible from cycle 3034 to cycle 3467.
#     Wait, let me recalculate.
#     Start bit: cycle 2 to 435 (baud_tick at 435 changes to bit 0)
#     Bit 0: cycle 436 to 869 (baud_tick at 869 changes to bit 1)
#     Bit 1: cycle 870 to 1303
#     Bit 2: cycle 1304 to 1737
#     Bit 3: cycle 1738 to 2171
#     Bit 4: cycle 2172 to 2605
#     Bit 5: cycle 2606 to 3039
#     Bit 6: cycle 3040 to 3473
#     Bit 7: cycle 3474 to 3907
#     Stop: cycle 3908 to 4341
#
#   t=651 (cycle 653): bit 0 [436-869] ✓
#   t=1085 (cycle 1087): bit 1 [870-1303] ✓
#   t=1519 (cycle 1521): bit 2 [1304-1737] ✓
#   t=1953 (cycle 1955): bit 3 [1738-2171] ✓
#   t=2387 (cycle 2389): bit 4 [2172-2605] ✓
#   t=2821 (cycle 2823): bit 5 [2606-3039] ✓
#   t=3255 (cycle 3257): bit 6 [3040-3473] ✓
#   t=3689 (cycle 3691): bit 7 [3474-3907] ✓
#
# All correct! So for a single byte, the sampling is perfect.
# The issue must be with the INTERACTION between bytes.
#
# After the last sample at t=3689 (cycle 3691), the tb waits BAUD_DIV=434:
#   t=4123 (cycle 4125): stop bit wait done.
#   The stop bit is [3908-4341]. 4125 is in this range. ✓
#   recv_byte returns.
#
# Then the tb calls send_byte. send_byte starts at cycle 4125.
# send_byte sets data_i=0 and waits 434 cycles.
# 
# The UART RX has its own baud_gen, which started at 0 on reset.
# Both baud_gens are identical and started at the same time.
# So they're in sync: both have the same cnt at the same cycle.
#
# At cycle 4125: baud_cnt = 4125 mod 434 = 4125 - 9*434 = 4125 - 3906 = 219.
# So baud_cnt=219 when send_byte starts.
#
# send_byte changes data_i every 434 cycles (counting posedges).
# The UART RX samples on baud_ticks (when baud_cnt wraps to 0).
#
# send_byte's start bit (data_i=0) is set at cycle 4125.
# The UART RX needs to detect this start bit.
# The UART RX detects the start bit on a baud_tick when prev_line=1 and rx_in=0.
# But the UART RX only checks on baud_ticks!
#
# The next baud_tick after cycle 4125 is at cycle 4125 + (434-219) = 4125+215 = 4340.
# At cycle 4340: baud_tick=1. The UART RX checks: prev_line=1 (idle), rx_in=0 (start bit).
# It detects the start bit and goes to DATA state.
#
# But wait, the start bit was set at cycle 4125 and lasts 434 cycles (until 4559).
# The baud_tick at 4340 is within the start bit period. Good.
#
# Then the UART RX samples bit 0 at the next baud_tick: cycle 4340+434 = 4774.
# send_byte changes to bit 0 at cycle 4125+434 = 4559.
# So bit 0 is visible from 4559 to 4993.
# The UART RX samples at 4774, which is in [4559, 4993]. ✓
#
# This continues for all 8 bits. The UART RX should receive the byte correctly.
# And indeed, the DBG log shows correct sobel values, confirming correct pixel reception.
#
# Now, rx_valid fires when the UART RX finishes receiving (at the baud_tick
# after bit 7). That's at cycle 4340 + 8*434 = 4340 + 3472 = 7812.
# Wait, the UART RX detects the start bit at the baud_tick at cycle 4340.
# Then it samples 8 bits at baud_ticks: 4774, 5208, 5642, 6076, 6510, 6944, 7378, 7812.
# At 7812 (bit 7 sample), bit_idx=7, so rx_valid=1 and rx_byte is set.
#
# The controller sees rx_valid at cycle 7812 (on the posedge).
# Actually, rx_valid is a reg, set on the baud_tick at cycle 7812.
# It takes effect after the posedge, so the controller sees it at cycle 7813.
# Wait, no. The UART RX sets rx_valid<=1 inside the if(baud_tick) block.
# baud_tick is a reg that was set to 1 by the baud_gen on the previous cycle.
# So at cycle 7812, baud_tick=1 (set at cycle 7811), and the UART RX sets rx_valid<=1.
# rx_valid takes effect at cycle 7813. The controller sees rx_valid=1 at cycle 7813.
#
# Hmm, actually I need to be more careful. Let me re-examine.
# The baud_gen sets baud_tick<=1 when cnt==433. This takes effect on the next cycle.
# So if cnt==433 at cycle N, baud_tick=1 at cycle N+1.
# The UART RX sees baud_tick=1 at cycle N+1 and processes it.
# It sets rx_valid<=1 (takes effect at cycle N+2).
# The controller sees rx_valid=1 at cycle N+2.
#
# OK, this is getting very detailed. Let me just focus on the key question:
# why does every other byte fail?
#
# The key insight from my earlier analysis: the total cycle count for
# recv_byte + send_byte is not a multiple of BAUD_DIV, causing a phase shift.
#
# recv_byte takes: 651 + 8*434 + 434 = 4557 cycles (from start bit detection)
# But start bit detection has a 2-cycle offset from the baud_tick.
# So recv_byte takes 4557 cycles from cycle 2 (after baud_tick).
# recv_byte ends at cycle 2 + 4557 = 4559.
#
# send_byte takes 10*434 = 4340 cycles.
# send_byte ends at cycle 4559 + 4340 = 8899.
#
# The next rx_valid fires at cycle 7813 (as calculated above).
# Wait, that doesn't match. Let me recalculate.
#
# Actually, the send_byte starts at cycle 4559 (when recv_byte ends).
# But the UART RX detects the start bit at the next baud_tick after 4559.
# baud_cnt at 4559: 4559 mod 434 = 4559 - 10*434 = 4559 - 4340 = 219.
# Next baud_tick: 4559 + (434-219) = 4559 + 215 = 4774.
# Wait, baud_tick happens when cnt goes from 433 to 0.
# cnt at 4559 is 219. cnt reaches 433 at cycle 4559 + (433-219) = 4559+214 = 4773.
# baud_tick=1 at cycle 4774.
#
# So the UART RX detects the start bit at cycle 4774.
# Then samples 8 bits at 4774+434=5208, 5642, ..., 4774+8*434=4774+3472=8246.
# rx_valid fires at cycle 8246+1 = 8247 (approximately).
#
# The controller sees rx_valid at cycle 8248 (approximately).
# It captures the result and sets tx_start.
# The UART TX latches tx_start and starts on the next baud_tick.
# baud_cnt at 8248: 8248 mod 434 = 8248 - 19*434 = 8248 - 8246 = 2.
# Next baud_tick: 8248 + (434-2) = 8248 + 432 = 8680.
# The UART TX sets tx_out=0 (start bit) at cycle 8680+1 = 8681 (approximately).
# The tb detects the start bit at cycle 8682.
#
# Now, the tb's recv_byte starts after send_byte ends.
# send_byte ends at cycle 4559 + 4340 = 8899.
# But the TX start bit appears at cycle 8682, which is BEFORE 8899!
# So the tb is still in send_byte when the TX starts!
# The tb won't see the start bit because it's busy sending.
# After send_byte, the tb calls recv_byte. But the TX has already started.
# The tb might catch the TX in the middle of a frame.
#
# THIS is the bug! The controller starts TX while the tb is still sending
# the next pixel. The tb misses the start bit and catches the frame mid-stream.
#
# Wait, but the DBG log shows the controller correctly processes every pixel
# and sends every result. And the tb captures 900 values. So the tb does
# catch every TX, just at the wrong time for half of them.
#
# Let me reconsider. The send_byte takes 4340 cycles. The UART RX takes
# about 10 baud periods to receive. The rx_valid fires near the end of
# send_byte. Then the controller starts TX. The TX start bit appears
# ~2 cycles after the next baud_tick after rx_valid.
#
# If rx_valid fires near the END of send_byte, the TX start bit might
# appear DURING the last part of send_byte (the stop bit of the pixel).
# The tb is setting data_i=1 (stop bit) during this time. The TX is
# sending on data_o. These are different signals, so no conflict.
# But the tb's recv_byte hasn't started yet.
#
# After send_byte, the tb calls recv_byte. If the TX start bit already
# happened, recv_byte might see data_o=0 (in the middle of the frame)
# and think it's a start bit. This would cause it to sample at the
# wrong time.
#
# OR: if the TX start bit happens during send_byte's stop bit (data_o=0
# during start bit, but the tb is not looking at data_o during send_byte),
# then after send_byte, recv_byte starts. It sees data_o might be 0 or 1
# depending on where in the TX frame we are.
#
# If the TX is in the middle of sending (e.g., at bit 3), data_o could be
# 0 or 1. If it's 0, recv_byte thinks it's a start bit and samples from
# there. This would give garbage.
#
# If the TX has finished (back to idle, data_o=1), recv_byte times out.
# Then the next send_byte happens, and the next TX starts. This time
# the timing might work out.
#
# This explains the alternating pattern! For some bytes, the TX happens
# to finish before recv_byte starts (correct). For others, the TX is
# still in progress when recv_byte starts (garbage).
#
# The fix: the controller should NOT start TX until the tb is ready to
# receive. But the controller doesn't know when the tb is ready.
#
# Alternative fix: the controller should wait for the UART RX to be
# idle before starting TX. But the UART RX is always receiving.
#
# The REAL fix: the tb should call recv_byte BEFORE send_byte, or
# the tb should overlap send_byte and recv_byte properly.
#
# But the instructions say not to weaken the tb. However, fixing the
# tb's send/receive ordering is not weakening - it's fixing a protocol bug.
#
# Actually, the fundamental issue is that the tb sends a pixel and then
# tries to receive. But the controller might produce a result DURING
# the pixel transmission (because the UART RX receives the pixel and
# the controller processes it while the tb is still sending).
#
# The correct approach: the tb should send ALL pixels first, then receive
# ALL results. Or: the tb should use a separate process to receive
# results while sending pixels.
#
# But the current tb sends one pixel, then tries to receive one result.
# This doesn't work because the result might come while the tb is still
# sending the next pixel.
#
# Let me look at the tb flow again:
# for i = 0 to 1023:
#   send_byte(pixel[i])
#   recv_byte(rx_byte, rx_ok)
#   if rx_ok: store
#
# The issue: send_byte takes 4340 cycles. During this time, the UART RX
# receives the byte. rx_valid fires near the end. The controller processes
# it and starts TX. The TX might start BEFORE send_byte finishes.
# Then recv_byte starts after send_byte. If the TX is already in progress,
# recv_byte catches it mid-frame.
#
# The fix: the tb should start recv_byte BEFORE send_byte, or use
# concurrent send/receive. But in Verilog, tasks are sequential.
#
# Actually, the simplest fix is to make the controller wait a bit before
# starting TX, to give the tb time to finish send_byte and start recv_byte.
# But that's a hack.
#
# The proper fix: the tb should send all pixels first, then receive all
# results. But the controller doesn't have a frame buffer - it sends
# results as they're computed. So the tb needs to receive concurrently.
#
# In Verilog, we can use fork/join or separate always blocks to handle
# concurrent send and receive. Let me restructure the tb to use a
# concurrent receive process.

# Actually, let me reconsider. The controller sends the result AFTER
# receiving the pixel. The result TX starts after rx_valid, which is
# near the end of send_byte. The TX takes 10 baud periods.
# send_byte takes 10 baud periods.
# So the TX finishes about 10 baud periods after send_byte finishes.
# Then recv_byte starts and waits for the next TX.
# But there IS no next TX until the next pixel is sent.
# So recv_byte times out.
#
# Wait, that doesn't match. The tb captures 900 values, so it does
# receive 900 bytes. Let me re-examine.
#
# The key: the TX start bit might appear DURING send_byte (before
# recv_byte starts). If the TX is already sending when recv_byte starts,
# recv_byte might catch the start bit if data_o happens to be 0 at that
# moment, or it might see data_o=1 and time out.
#
# If the TX start bit appears at cycle X, and recv_byte starts at cycle Y:
# - If Y < X: recv_byte waits and catches the start bit at X. Correct.
# - If X < Y < X+434 (during start bit): recv_byte catches the start bit.
#   But it's already partway through the start bit, so the timing is off.
# - If X+434 < Y < X+4340 (during data bits): recv_byte might see data_o=0
#   and think it's a start bit. This gives garbage.
# - If Y > X+4340 (TX done): recv_byte times out.
#
# For the alternating pattern:
# - Even indices: Y < X (recv_byte starts before TX). Correct.
# - Odd indices: X < Y (TX starts before recv_byte). Garbage.
#
# This makes sense! The phase alternates because the cycle count isn't
# a multiple of BAUD_DIV.
#
# The fix: make the controller wait until the tb is ready to receive
# before starting TX. But the controller can't know this.
#
# Better fix: restructure the tb to receive concurrently with sending.
# Use a separate always block or fork/join to capture TX bytes while
# sending pixels.

print("The root cause is a tb timing issue: the controller starts TX")
print("while the tb is still in send_byte, before recv_byte starts.")
print("Fix: restructure the tb to receive concurrently with sending.")