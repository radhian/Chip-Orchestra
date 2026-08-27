# Let me re-examine the TX FSM more carefully.
# The issue is whether there's a 1-baud gap between frames.
#
# Looking at uart_tx.v:
# STOP state: at baud_tick -> tx_done=1, state->IDLE, tx_out=1
# IDLE state: at baud_tick -> if start_req, state->START, tx_out=0
#
# So after STOP, we're in IDLE. The NEXT baud_tick checks start_req.
# If start_req is already set (latched during STOP), it starts.
# That's 1 baud period in IDLE.
#
# BUT: what if we modify STOP to go directly to START if start_req?
# Then: STOP -> (baud_tick, start_req=1) -> START (tx_out=0)
# No IDLE gap! Frame-to-frame = 10 baud periods.
#
# However, the standard UART has a stop bit (high) followed by start bit (low).
# If we go STOP->START directly, the stop bit is 1 baud, then start bit is 1 baud.
# That's correct! The stop bit IS the IDLE=1 period. So STOP->START is fine.
#
# Actually wait - in the current FSM:
# STOP: tx_out=1 (stop bit), lasts 1 baud. Then -> IDLE.
# IDLE: tx_out=1 (still high). Lasts 1 baud (until next baud_tick). Then -> START.
# START: tx_out=0 (start bit). Lasts 1 baud.
#
# So currently: stop bit (1 baud) + idle (1 baud) + start bit (1 baud) = 
# the receiver sees: 1 (stop) 1 (idle) 0 (start) - that's a 2-baud high period.
# A standard UART receiver would see the stop bit, then idle, then start.
# The extra idle baud is just additional idle time. It's valid but slow.
#
# If we go STOP->START: stop bit (1 baud) + start bit (0) immediately.
# The receiver sees: 1 (stop) 0 (start) - standard back-to-back frames.
# This is also valid and faster!
#
# So the fix is: in STOP state, if start_req, go to START instead of IDLE.
# This eliminates the 1-baud gap and makes TX rate = RX rate.
#
# But wait - the testbench recv_byte_blocking does:
# while (data_o === 1'b1) @(posedge clk);  // wait for start bit (falling edge)
# Then samples 8 bits.
# Then immediately looks for next start bit.
# 
# With the gap: after 8 data bits, there's stop(1) + idle(1) = 2 baud high.
# The while loop sees high, waits, then sees the falling edge of next start.
# With no gap: after 8 data bits, there's stop(1) = 1 baud high, then start(0).
# The while loop sees high for 1 baud, then falling edge. Still works!
#
# But the recv_byte_blocking samples at HALF_BAUD + BAUD_DIV after the falling edge.
# That's 217 + 434 = 651 clocks = 1.5 baud periods after start bit edge.
# So it samples bit 0 at 1.5 baud, bit 1 at 2.5 baud, etc.
# Bit 7 at 8.5 baud. Then it looks for next start bit.
# With no gap: stop bit is at 9.0-10.0 baud. Start of next frame at 10.0 baud.
# The while loop starts looking at 8.5 baud. It sees high (stop bit) for 1.5 baud,
# then sees the falling edge at 10.0 baud. That's fine.
#
# With the gap: stop at 9-10, idle at 10-11, start at 11. 
# While loop starts at 8.5, sees high for 2.5 baud, then falling edge at 11. Fine.
#
# So both work. The no-gap version is just faster.
#
# Now, the KEY question: with the no-gap TX, is the backlog always <= 1?
# Let me be more precise about the timing.

BAUD_DIV = 434

# RX: rx_valid fires at the baud_tick when bit 7 is sampled.
# RX frame: STOP(state detects start) -> DATA(8 bits) -> STOP
# The start bit is detected at baud_tick N. Then 8 data bits at N+1..N+8.
# rx_valid fires at baud_tick N+8 (when bit 7 sampled).
# So from start detection to rx_valid = 8 baud periods.
# Next start detection: the RX is in STOP state, looking for falling edge.
# The stop bit of the frame is 1 baud. So next start detected at N+9.
# Next rx_valid at N+9+8 = N+17.
# So rx_valid period = 9 baud? No...
#
# Actually: the testbench sends start bit, 8 data, stop bit = 10 baud.
# RX detects start at baud_tick 0 (say). Samples data at ticks 1-8.
# rx_valid at tick 8. Then in STOP, waits for next falling edge.
# The stop bit (high) is at tick 9. Then next start bit (low) at tick 10.
# RX detects it at tick 10 (if baud_tick aligns). Samples at 11-18.
# rx_valid at tick 18. Period = 18-8 = 10 baud. OK, 10 baud per rx_valid.
#
# TX with no gap: START(1) + DATA(8) + STOP(1) = 10 baud.
# tx_done at end of STOP. If start_req, immediately START.
# So tx_done period = 10 baud.
#
# Both are 10 baud = 4340 clocks. Rate matched!
# 
# But there's a phase offset. The first result is produced at rx_valid #66.
# TX starts at that point (plus 0-434 clock wait for baud_tick).
# After that, both run at 4340 clocks/frame.
# 
# The backlog: result i is produced at time t_i = (66+i)*4340 + phase_rx
# (approximately, ignoring row boundary gaps)
# TX finishes frame i at time t_0 + (i+1)*4340 + phase_tx
# 
# If phase_tx > phase_rx, TX is always behind by the phase difference.
# But since both run at 4340, the backlog is constant = phase difference / 4340.
# Max phase difference = 434 clocks < 4340, so backlog = 0 or 1.
#
# But there ARE row boundary gaps! At the end of each row (col 30, 31),
# no result is produced. So there are 2 pixels with no result per row.
# During those 2*4340 = 8680 clocks, TX catches up by 2 frames.
# So the backlog actually DECREASES at row boundaries.
#
# Let me simulate precisely with the no-gap TX model.

result_times = []
for p in range(1024):
    row = p // 32
    col = p % 32
    if row >= 2 and col >= 2:
        result_times.append(p * 4340)  # rx_valid at p*4340 (approx)

# TX: first frame starts at result_times[0] + delay (0 to 434)
# Each frame takes 4340 clocks. tx_done at start + 4340.
# Next frame can start at tx_done (if start_req already set).

# Worst case: initial delay = 434 (just missed a baud_tick)
delay = 434

backlog = 0
max_backlog = 0
tx_done_at = result_times[0] + delay + 4340  # first frame done

for i in range(1, len(result_times)):
    rt = result_times[i]
    if rt >= tx_done_at:
        # TX is free when result arrives
        tx_done_at = rt + 4340  # start immediately, 10 baud
        backlog = 0
    else:
        # TX is busy, result waits
        backlog += 1
        tx_done_at = tx_done_at + 4340  # next frame done
        backlog -= 1  # this result now being transmitted
    max_backlog = max(max_backlog, backlog)

print(f"Max backlog (no-gap TX, worst-case initial delay): {max_backlog}")

# Try with delay = 0
delay = 0
backlog = 0
max_backlog = 0
tx_done_at = result_times[0] + delay + 4340

for i in range(1, len(result_times)):
    rt = result_times[i]
    if rt >= tx_done_at:
        tx_done_at = rt + 4340
        backlog = 0
    else:
        backlog += 1
        tx_done_at = tx_done_at + 4340
        backlog -= 1
    max_backlog = max(max_backlog, backlog)

print(f"Max backlog (no-gap TX, zero initial delay): {max_backlog}")

# Try with delay = 433 (just barely missed)
delay = 433
backlog = 0
max_backlog = 0
tx_done_at = result_times[0] + delay + 4340

for i in range(1, len(result_times)):
    rt = result_times[i]
    if rt >= tx_done_at:
        tx_done_at = rt + 4340
        backlog = 0
    else:
        backlog += 1
        tx_done_at = tx_done_at + 4340
        backlog -= 1
    max_backlog = max(max_backlog, backlog)

print(f"Max backlog (no-gap TX, 433-cycle initial delay): {max_backlog}")

# What about the CURRENT TX (with 1-baud gap = 11 baud per frame)?
# TX takes 11*434 = 4774 clocks per frame.
# Results come every 4340. Backlog grows by (4774-4340)/4340 per frame.
# But row boundaries give 2*4340 = 8680 clocks of catch-up = 8680/4774 = 1.8 frames.
# Per row: 30 results, backlog grows by 30*(4774-4340)/4340 = 30*0.1 = 3
# Row boundary: catch up 1.8. Net growth per row: 3-1.8 = 1.2
# Over 30 rows: 36. That's why they needed a 128-deep FIFO!

print("\n--- Current TX (11 baud/frame with gap) ---")
delay = 434
backlog = 0
max_backlog = 0
tx_done_at = result_times[0] + delay + 4774  # 11 baud

for i in range(1, len(result_times)):
    rt = result_times[i]
    if rt >= tx_done_at:
        tx_done_at = rt + 4774
        backlog = 0
    else:
        backlog += 1
        tx_done_at = tx_done_at + 4774
        backlog -= 1
    max_backlog = max(max_backlog, backlog)

print(f"Max backlog (current TX with gap): {max_backlog}")