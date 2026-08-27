# CONFIRMED: Every odd-indexed chip output is the golden value sampled 1 bit late.
# The tb's recv_byte is sampling one baud period too late for every other byte.
#
# This is a UART timing issue. The tb's recv_byte detects the start bit and
# then waits HALF_BAUD + BAUD_DIV before sampling the first data bit.
# But for every other byte, the start bit detection is off by one baud period,
# causing all subsequent samples to be one bit late.
#
# The root cause: the UART TX doesn't have a full stop bit gap between
# consecutive transmissions, OR the tb's recv_byte start-bit detection
# is catching the END of the previous frame's stop bit as the start bit
# of the next frame.
#
# Let me look at the UART TX timing:
# STOP state: tx_out=1, tx_done=1, state=IDLE (on baud_tick)
# IDLE state: if start_req, tx_out=0 (start bit), state=START (on baud_tick)
#
# So the stop bit lasts 1 baud period, then immediately the next start bit
# can begin. There's only 1 stop bit between frames.
#
# The tb's recv_byte:
# 1. Wait for data_o to go from 1 to 0 (start bit detection)
# 2. Wait HALF_BAUD + BAUD_DIV = 651 cycles
# 3. Sample 8 bits every BAUD_DIV cycles
# 4. Wait BAUD_DIV for stop bit
#
# After step 4, the tb returns. Then it sends the next pixel (send_byte).
# After send_byte, it calls recv_byte again.
#
# The issue: when the controller sends two results back-to-back (which
# it doesn't - it waits for the next pixel), the stop bit of the first
# and the start bit of the second are adjacent.
#
# But actually, the controller sends one result per pixel. Between results,
# the tb sends a pixel (10 baud periods on data_i). The TX line (data_o)
# is idle high during this time. So there should be a clear gap.
#
# Wait - but the controller might start the NEXT TX before the tb finishes
# recv_byte! Let me trace the timing:
#
# 1. tb sends pixel (10 baud on data_i)
# 2. rx_valid fires at end of send_byte
# 3. Controller: S_RECV -> S_TX_RESULT (1 cycle) -> S_NEXT
# 4. UART TX: latches tx_start, waits for baud_tick, sends 10 bits
# 5. tb's recv_byte: detects start bit, samples 8 bits, waits stop
# 6. recv_byte returns after ~10 baud periods
# 7. tb sends next pixel
#
# The TX (step 4) and recv_byte (step 5) happen in parallel.
# The TX takes 10 baud periods. recv_byte takes ~10 baud periods.
# They should finish at about the same time.
#
# But the TX might start a few cycles AFTER recv_byte begins (because
# the controller needs 2 cycles to set tx_start, then the UART TX waits
# for the next baud_tick). So recv_byte might be a few cycles ahead of TX.
#
# For the FIRST result: recv_byte starts, waits for data_o=0. The TX
# starts a few cycles later. recv_byte catches the start bit correctly.
#
# For the SECOND result: after recv_byte returns, the tb sends the next
# pixel. The controller is in S_NEXT, waiting for tx_done. tx_done fires
# at the end of TX. The controller goes to S_RECV. Then rx_valid fires
# (from the new pixel), and the controller starts a new TX.
#
# The timing should be similar for each result. So why does every other
# one fail?
#
# Let me think about the baud_gen synchronization. Both the UART TX and
# the tb use the same baud_divider. But the tb counts cycles manually
# (repeat (BAUD_DIV) @(posedge clk)), while the UART TX uses baud_gen.
#
# The baud_gen counts 0,1,2,...,433, then wraps to 0 and emits baud_tick.
# The tb's repeat(BAUD_DIV) counts 434 posedges.
#
# These should be exactly synchronized IF they start at the same time.
# But they don't - the baud_gen runs continuously, while the tb's counting
# starts when send_byte or recv_byte begins.
#
# The key issue: the tb's recv_byte detects the start bit at a random
# phase of the baud_gen. Then it counts HALF_BAUD+BAUD_DIV cycles.
# But the UART TX's bits change on baud_ticks, which are at a specific
# phase. If the tb's counting is off by a few cycles from the baud_gen,
# the sampling might be at the wrong time.
#
# For the FIRST byte: the tb detects the start bit early in the start
# bit period. It waits 651 cycles, landing near the middle of bit 0.
# Good.
#
# For the SECOND byte: the tb detects the start bit LATE in the start
# bit period (because the previous recv_byte ended at a different phase).
# It waits 651 cycles, landing near the END of bit 0 or beginning of bit 1.
# Bad - it samples bit 1 instead of bit 0, causing the "1 bit late" error.
#
# This is a classic UART synchronization issue. The fix should be in the
# UART TX: add a small delay or ensure the start bit is held long enough
# for the receiver to detect it at the right time.
#
# Actually, the real fix is simpler: the UART TX should wait for the
# baud_gen to be at a known phase before starting. Or the tb's recv_byte
# should sample at the baud_tick phase.
#
# But wait - the instructions say I should fix the RTL, not the tb
# (unless the tb's expectation is wrong). The golden model is correct.
# The tb's recv_byte is a standard UART receiver. The issue is that
# the UART TX starts transmitting at a random baud_gen phase, and the
# tb's recv_byte can't synchronize properly.
#
# Actually, looking more carefully: the UART TX changes tx_out on baud_tick.
# The start bit (tx_out=0) is set on a baud_tick. It stays 0 until the
# next baud_tick (1 full baud period). Then bit 0 is set, etc.
#
# The tb's recv_byte detects the start bit when data_o goes to 0.
# This happens right after a baud_tick (within 1 clock cycle).
# Then it waits HALF_BAUD + BAUD_DIV = 651 cycles.
# The next baud_tick (start of bit 0) is 434 cycles after the start bit began.
# So the tb samples at 651 cycles after detecting the start bit.
# The start bit was detected ~1 cycle after it began.
# So the tb samples at ~652 cycles after the start bit began.
# Bit 0 begins at 434 cycles. Bit 1 begins at 868 cycles.
# 652 is in the middle of bit 0 (434 to 868). Good.
#
# Then the tb samples every 434 cycles: 652, 1086, 1520, ...
# Bit transitions: 434, 868, 1302, 1736, ...
# Sample 652: in bit 0 (434-868) ✓
# Sample 1086: in bit 1 (868-1302) ✓
# Sample 1520: in bit 2 (1302-1736) ✓
# ... all good.
#
# So for a single byte, the sampling is correct. The issue must be with
# the INTERACTION between consecutive bytes.
#
# After recv_byte finishes, it has waited for the stop bit:
# repeat (BAUD_DIV) @(posedge clk) -> 434 cycles
# The last data bit sample was at 652 + 7*434 = 652 + 3038 = 3690
# The stop bit wait ends at 3690 + 434 = 4124
# The stop bit begins at 434 + 8*434 = 434 + 3472 = 3906
# The stop bit ends at 3906 + 434 = 4340
# So recv_byte ends at 4124, which is in the middle of the stop bit.
# The TX is still sending the stop bit (until 4340).
#
# Then the tb sends the next pixel. send_byte starts with:
# data_i = 0 (start bit)
# repeat (BAUD_DIV) @(posedge clk) -> 434 cycles
# ...
#
# Meanwhile, the TX finishes the stop bit at 4340, goes to IDLE.
# The controller gets tx_done at 4340, goes to S_RECV.
# The UART RX receives the new pixel's start bit...
#
# This all seems fine. The issue might be more subtle.
# Let me just run the simulation with some debug to see the exact timing.

# Actually, let me reconsider. The problem might be simpler than I think.
# Let me look at the recv_byte task again:
#
# recv_byte:
#   while (data_o === 1'b1 && timeout_cnt < (BAUD_DIV * 3)):
#     @(posedge clk)
#     timeout_cnt++
#   if (data_o === 1'b1): timeout, return ok=0
#   else:
#     repeat (HALF_BAUD + BAUD_DIV) @(posedge clk)  // wait to middle of bit 0
#     for 8 bits:
#       byte_val[b] = data_o
#       repeat (BAUD_DIV) @(posedge clk)
#     repeat (BAUD_DIV) @(posedge clk)  // stop bit
#     ok = 1
#
# The issue: after detecting the start bit, it waits HALF_BAUD + BAUD_DIV.
# HALF_BAUD = 217, BAUD_DIV = 434. Total = 651.
# This is supposed to get to the middle of bit 0.
# The start bit lasts 434 cycles. Bit 0 starts at 434.
# Middle of bit 0 = 434 + 217 = 651.
# So waiting 651 cycles from start bit detection should land at middle of bit 0.
# But the start bit is detected 1 cycle after it begins (due to posedge sampling).
# So the wait is 651 cycles from 1 cycle after start = at cycle 652.
# Middle of bit 0 is at 651. So we're 1 cycle late. Close enough.
#
# But what if the start bit is detected LATE? If data_o changes to 0
# right after a posedge, the tb won't see it until the next posedge
# (1 cycle later). But the UART TX changes tx_out on a posedge (baud_tick
# is registered). So data_o changes right after a posedge, and the tb
# sees it on the next posedge. 1 cycle delay. Fine.
#
# The real question: why does every OTHER byte fail?
# Let me check if the issue is that the tb's send_byte and the UART's
# baud_gen get out of sync, causing the rx_valid to fire at different
# phases relative to the baud_gen.

# Let me just check: after the tb's recv_byte finishes (at some cycle),
# it immediately starts send_byte. send_byte sets data_i=0 and waits
# BAUD_DIV cycles. The UART RX detects this start bit on its baud_tick.
# The UART RX's baud_gen is running continuously.
# 
# The send_byte takes 10*BAUD_DIV = 4340 cycles.
# The UART RX needs to sample 8 bits at baud_ticks.
# If the send_byte's bit transitions align with the UART RX's baud_ticks,
# the byte is received correctly.
#
# send_byte changes data_i every BAUD_DIV cycles (counting posedges).
# The UART RX samples on baud_ticks (every 434 cycles, but at a specific phase).
# If send_byte starts at a random phase, the bit transitions might not
# align with the baud_ticks.
#
# For the FIRST pixel: send_byte starts right after reset. The baud_gen
# starts at 0. send_byte starts at some cycle. The alignment depends on
# when send_byte starts relative to the baud_gen.
#
# But the UART RX detects the start bit on a baud_tick (falling edge).
# Then it samples 8 bits on subsequent baud_ticks. The send_byte changes
# bits every 434 posedges. If the baud_tick and send_byte's bit changes
# are aligned, the sampling is correct.
#
# The issue: send_byte counts 434 posedges per bit. The baud_gen counts
# 434 cycles per tick. If they start at the same time, they stay aligned.
# But if send_byte starts at a different phase than the baud_gen, the
# bit changes and baud_ticks are offset.
#
# For example, if send_byte starts when baud_gen.cnt=100:
# send_byte changes data_i at cycles 0, 434, 868, ...
# baud_ticks occur at cycles 334, 768, 1202, ... (when cnt reaches 433)
# The offset is 334 cycles. The UART RX samples 334 cycles after each
# bit change. Since each bit lasts 434 cycles, sampling at 334 is within
# the bit period (0-434). So it should work, but the margin is reduced.
#
# If the offset is close to 434, the UART RX might sample the NEXT bit.
# This would cause the received byte to be wrong.
#
# But this would affect the PIXEL data, not the RESULT data. If the
# pixel is received wrong, the sobel result would be wrong. But the
# DBG log shows the correct sobel results, meaning the pixels are
# received correctly.
#
# So the pixel reception is fine. The issue is purely in the RESULT
# transmission (UART TX -> tb recv_byte).
#
# Let me focus on the UART TX -> recv_byte path.
# The UART TX sends bits on baud_ticks. The tb's recv_byte samples
# on posedge clk, counting cycles manually.
# 
# The UART TX's baud_gen runs continuously. When the controller sets
# tx_start, the UART TX latches it and starts sending on the next
# baud_tick. The start bit appears on a baud_tick.
#
# The tb's recv_byte detects the start bit 1 cycle after the baud_tick.
# Then it counts 651 cycles to the middle of bit 0.
# The next baud_tick (bit 0 start) is 434 cycles after the start bit's
# baud_tick. So bit 0 starts at 434, and the tb samples at 652.
# 652 - 434 = 218, which is in the middle of bit 0. Good.
#
# Then the tb samples every 434 cycles: 652, 1086, 1520, ...
# Baud_ticks: 0, 434, 868, 1302, 1736, ...
# Bit 0: 434-868, sample at 652 ✓
# Bit 1: 868-1302, sample at 1086 ✓
# Bit 2: 1302-1736, sample at 1520 ✓
# ...
# Bit 7: 3472-3906, sample at 3690 ✓
# Stop: 3906-4340
# 
# After the last sample at 3690, the tb waits 434 for the stop bit,
# ending at 4124. The stop bit ends at 4340.
# 
# So recv_byte ends at 4124 (relative to start bit detection at ~1).
# The TX ends at 4340 (tx_done fires at the baud_tick ending the stop bit).
# 
# Now, the tb sends the next pixel. send_byte starts at ~4124.
# The controller gets tx_done at 4340, goes to S_RECV.
# The UART RX receives the new pixel.
# rx_valid fires at some point during send_byte.
# The controller captures the result and starts a new TX.
# 
# The new TX's start bit appears on the next baud_tick after tx_start.
# The baud_tick happens at 434*k cycles. The tx_start is set ~2 cycles
# after rx_valid. rx_valid happens at a baud_tick of the UART RX.
# 
# The UART RX and UART TX share separate baud_gen instances but with
# the same parameters. They might be at different phases!
# 
# Actually, looking at the RTL: both uart_rx and uart_tx instantiate
# their own baud_gen. These are separate instances with separate counters.
# They both start at 0 on reset, but they might drift apart if they
# count differently. But they use the same logic, so they should stay
# in sync.
# 
# Wait, they both start at cnt=0 on reset. They both count to 433 and
# wrap. So they should be perfectly in sync. Every baud_tick from
# uart_rx's baud_gen coincides with every baud_tick from uart_tx's baud_gen.
# 
# So the UART RX's baud_tick and UART TX's baud_tick happen on the
# same cycle. This means:
# - rx_valid fires on a baud_tick (when the UART RX finishes receiving)
# - The controller processes it and sets tx_start 2 cycles later
# - The UART TX starts sending on the next baud_tick (up to 434 cycles later)
# 
# The tb's send_byte takes 10*434 = 4340 cycles. The UART RX's baud_ticks
# happen every 434 cycles. If send_byte starts at a random phase, the
# UART RX might sample at the wrong time.
# 
# But we know the pixels are received correctly (DBG shows correct sobel).
# So the send_byte -> UART RX path works.
# 
# The issue is the UART TX -> recv_byte path. Let me think about why
# every other byte fails.
# 
# After the first recv_byte (for result 0), the tb ends at cycle ~4124
# (relative to the start bit). The TX ends at ~4340. The tb starts
# send_byte at ~4124. send_byte takes 4340 cycles, ending at ~8464.
# The UART RX receives the pixel, rx_valid fires at a baud_tick near
# the end of send_byte.
# 
# The controller sets tx_start 2 cycles after rx_valid. The UART TX
# starts on the next baud_tick. The start bit appears.
# 
# The tb's recv_byte starts after send_byte (at ~8464). It waits for
# data_o=0. The TX start bit appears at some baud_tick after tx_start.
# 
# The key: the tb's recv_byte and the UART TX's baud_gen are NOT
# synchronized. The tb counts cycles manually, while the UART TX
# uses its baud_gen. After the first byte, the phase relationship
# between the tb's counting and the baud_gen might shift.
# 
# Actually, I think the issue is simpler. Let me look at the recv_byte
# stop bit wait:
# 
# After sampling bit 7 at cycle 3690, the tb does:
#   repeat (BAUD_DIV) @(posedge clk)  // wait for stop bit
# This waits 434 cycles, ending at 4124.
# 
# But the stop bit starts at 3906 and ends at 4340.
# So the tb ends at 4124, which is 216 cycles BEFORE the stop bit ends.
# 
# Then the tb starts send_byte. The TX is still sending the stop bit
# (until 4340). The tb sets data_i=0 (start bit of the new pixel).
# 
# Now, the UART RX sees data_i=0. But the UART RX's baud_gen is at
# some phase. The UART RX might detect this as a start bit immediately
# (if its baud_gen is at the right phase) or miss it.
# 
# But more importantly: the tb's send_byte starts at 4124, and the
# TX's stop bit ends at 4340. There's a 216-cycle overlap where the
# TX is still sending the stop bit while the tb is sending the start
# bit of the new pixel. But data_i and data_o are different signals,
# so this overlap doesn't cause a problem.
# 
# OK, I think I need to just look at this empirically. Let me add
# more debug to the simulation and check the exact timing.
# 
# Actually, let me try a different approach. The issue is that the
# tb's recv_byte samples 1 bit late for every other byte. This suggests
# the start bit detection is off by 1 baud period for every other byte.
# 
# The most likely cause: the UART TX's stop bit is too short, or the
# tb's recv_byte catches the END of the previous frame's last data bit
# as the start bit of the next frame.
# 
# Wait, the stop bit is 1 baud period (high). The start bit is 1 baud
# period (low). There's no overlap. The tb should see a clear high->low
# transition.
# 
# Unless... the UART TX goes from STOP to IDLE and then immediately to
# START on consecutive baud_ticks. In that case, the stop bit is only
# 1 baud period, and the next start bit begins immediately after.
# The tb's recv_byte might catch the start bit correctly.
# 
# But what if the controller sets tx_start for the next result BEFORE
# the current TX finishes? Then the UART TX might start a new frame
# immediately after the stop bit, with only 1 stop bit between frames.
# 
# Looking at the controller: it sets tx_start in S_TX_RESULT, then goes
# to S_NEXT. In S_NEXT, it waits for tx_done. So it can't set tx_start
# again until after tx_done. Good.
# 
# But what about the FIRST result? The controller is in S_RECV, gets
# rx_valid, captures result, goes to S_TX_RESULT. It sets tx_start=1.
# Then goes to S_NEXT. Waits for tx_done. Goes back to S_RECV.
# 
# The next rx_valid comes from the next pixel. The controller captures
# the result and sets tx_start again. The UART TX latches this and
# starts sending after the current frame is done (if it's still sending).
# 
# But the UART TX latches tx_start on ANY clock. If tx_start is still
# high when the TX is in IDLE, it starts a new frame. But tx_start is
# only high for 1 cycle (registered, defaulted to 0). So it should be fine.
# 
# I think the issue might be that the tb's recv_byte and send_byte
# are not properly synchronized with the baud_gen, causing a phase
# drift that accumulates over time.
# 
# Let me just try a fix: make the UART TX wait an extra baud period
# in the STOP state before going to IDLE. This gives the receiver
# more time to synchronize.

# Actually, let me look at this from the tb side. The recv_byte task
# has a specific timing:
# 1. Detect start bit (data_o goes low)
# 2. Wait HALF_BAUD + BAUD_DIV = 651 cycles
# 3. Sample 8 bits every BAUD_DIV = 434 cycles
# 4. Wait BAUD_DIV = 434 cycles for stop
# Total: 651 + 8*434 + 434 = 651 + 3472 + 434 = 4557 cycles
# 
# But the TX frame is: start(434) + 8*data(434) + stop(434) = 4340 cycles
# 
# So recv_byte takes 4557 cycles, but the TX frame is 4340 cycles.
# The difference is 217 cycles (HALF_BAUD).
# 
# After recv_byte, the tb immediately starts send_byte.
# send_byte takes 10*434 = 4340 cycles.
# 
# So the cycle from one recv_byte to the next is:
# recv_byte (4557) + send_byte (4340) = 8897 cycles
# 
# The TX frame is 4340 cycles. The controller produces a result when
# rx_valid fires, which is at the end of send_byte.
# 
# The time from one TX start to the next TX start is:
# TX frame (4340) + gap + next rx_valid + controller delay + baud_tick wait
# 
# This is getting complex. Let me just try the fix and see if it works.
# 
# The simplest fix: make the UART TX output a longer stop bit (2 baud
# periods instead of 1). This gives the receiver more time to detect
# the start bit of the next frame.

# Actually, I think the real issue is that the tb's recv_byte detects
# the start bit at different phases of the baud_gen for alternating
# bytes. This is because the total cycle count of recv_byte + send_byte
# is not a multiple of BAUD_DIV, causing a phase shift.
# 
# recv_byte takes 4557 cycles. 4557 / 434 = 10.5. So it's 10.5 baud periods.
# send_byte takes 4340 cycles = 10 baud periods.
# Total: 20.5 baud periods.
# 
# Since the baud_gen has a period of 434, and the total is 20.5 * 434,
# the phase shifts by 0.5 * 434 = 217 cycles each iteration.
# 
# After 2 iterations, the phase shifts by 434 = 1 full baud period.
# So the phase alternates between two values: 0 and 217.
# 
# When the phase is 0, the start bit is detected at the beginning of
# the baud period, and sampling is correct.
# When the phase is 217, the start bit is detected 217 cycles into
# the baud period, and the sampling is off by ~217 cycles, which might
# cause it to sample 1 bit late.
# 
# THIS explains the alternating pattern!
# 
# The fix: make recv_byte take a whole number of baud periods.
# Currently it takes 10.5 baud periods (HALF_BAUD extra).
# The HALF_BAUD is used to get to the middle of the first data bit.
# But this causes a phase shift.
# 
# The fix should be in the UART TX: ensure the start bit is held for
# a full baud period and the bits are clearly delimited. The current
# UART TX already does this. The issue is in the tb's recv_byte timing.
# 
# But wait - the instructions say I should fix the RTL, not the tb.
# The tb's recv_byte is a standard UART receiver pattern. The issue
# is that the UART TX starts at a random phase relative to the tb's
# counting.
# 
# Actually, the real fix is to make the UART TX's baud_gen start at 0
# when it begins a new transmission. This way, the start bit is always
# at a known phase, and the tb can synchronize to it.
# 
# But that's not how real UARTs work. Real UARTs have free-running
# baud generators.
# 
# The actual fix: the tb's recv_byte should wait for the MIDDLE of
# the start bit before counting, to properly synchronize. Currently
# it detects the start bit immediately (at the beginning) and then
# waits HALF_BAUD + BAUD_DIV. This works if the start bit is detected
# at the very beginning, but fails if detected later.
# 
# A better recv_byte would:
# 1. Detect start bit (data_o goes low)
# 2. Wait HALF_BAUD to get to the middle of the start bit
# 3. Verify data_o is still low (confirm start bit)
# 4. Wait BAUD_DIV to get to the middle of bit 0
# 5. Sample 8 bits every BAUD_DIV
# 
# But the instructions say not to weaken the testbench. However, fixing
# the recv_byte timing is not weakening it - it's making it correct.
# 
# Actually, let me re-read the instructions: "Do NOT weaken the testbench
# to make it pass — the golden model and the canonical input are the truth."
# 
# Fixing the recv_byte timing is not weakening it. It's fixing a bug in
# the tb's UART receiver. The tb is supposed to receive the correct bytes,
# but it's sampling at the wrong time.
# 
# But wait - the instructions also say "Fix the RTL (or the testbench IF
# its expectation was computed wrongly)". The tb's expectation is the
# golden output, which is correct. The tb's recv_byte is just the mechanism
# to capture the output. If recv_byte has a timing bug, it's a tb bug.
# 
# However, I should be careful. The issue might also be fixable in the RTL.
# If the UART TX resets its baud_gen at the start of each frame, the
# start bit would always be at a known phase, and the tb's recv_byte
# would work correctly.
# 
# Let me try the RTL fix first: reset the baud_gen in the UART TX when
# starting a new frame. This ensures the start bit is always at phase 0.

print("Root cause identified: tb's recv_byte has a phase synchronization issue")
print("with the UART TX's baud_gen. Every other byte is sampled 1 bit late.")
print("Fix: reset the UART TX's baud_gen when starting a new frame, so the")
print("start bit is always at a known phase.")