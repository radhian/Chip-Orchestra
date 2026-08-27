# Analyze the RX/TX timing to understand the rate mismatch and design backpressure
# 
# UART frame = 10 baud periods (1 start + 8 data + 1 stop)
# BAUD_DIV = 434 clocks per baud period
# So one byte over UART = 10 * 434 = 4340 clocks
#
# RX: receives one byte every 4340 clocks -> rx_valid every 4340 clocks
# TX: transmits one byte every 4340 clocks -> tx_done every 4340 clocks
#
# But the FIRST result is produced after 2 full rows + 2 pixels = 2*32+2 = 66 pixels
# = 66 * 4340 = 286,440 clocks after first pixel
#
# After that, results come every pixel (every 4340 clocks) for cols 2..31 (30 per row)
# then skip 2 pixels at row boundary.
#
# KEY INSIGHT: RX and TX run at the SAME baud rate (both 115200).
# So on average, results are produced at the same rate they can be transmitted.
# 
# The issue is the INITIAL LAG: 66 pixels arrive before the first result is produced.
# During that time, TX is idle. Then results start flowing.
#
# After the first result, each subsequent result comes 4340 clocks later (next pixel).
# TX also takes 4340 clocks per byte. So they're rate-matched!
#
# But there's a subtlety: the TX needs to be STARTED, and there's a small latency
# between result production and tx_start. Let me think about whether a single-entry
# buffer (holding register) with backpressure works.
#
# With a single holding register + backpressure:
# - When a result is produced and the holding reg is empty -> store it
# - When TX is idle and holding reg is full -> start TX, clear holding reg
# - When a result is produced and holding reg is full (TX busy) -> STALL the producer
#
# But we CAN'T stall the UART RX! The host sends pixels at a fixed baud rate.
# The testbench sends pixels back-to-back with no gaps.
#
# So backpressure on the producer (UART RX) is IMPOSSIBLE in this design -
# the host controls the send rate, not the DUT.
#
# Wait - let me re-read the regression log guidance:
# "If you added a queue/buffer to absorb a rate mismatch, the streaming answer 
#  is BACKPRESSURE, not depth: stall the producer while the consumer is busy"
#
# But the producer here is the UART RX which receives at the host's pace.
# We cannot stall it. So what's the actual rate mismatch?
#
# Let me reconsider. The testbench sends 1024 pixels back-to-back.
# Each pixel = 10 baud periods = 4340 clocks.
# Total send time = 1024 * 4340 = 4,444,160 clocks
#
# Results: 900 results, each needs 4340 clocks to transmit = 3,906,000 clocks
# First result at pixel 66 = 66*4340 = 286,440 clocks
# Last result produced at pixel 1023 = 1023*4340 = 4,439,820 clocks
# Last result transmitted: first result time + 900*4340 = 286,440 + 3,906,000 = 4,192,440
# 
# Wait, that's BEFORE the last pixel arrives (4,439,820). So TX finishes before RX!
# That means there's NO backlog - TX is actually FASTER than RX because it starts
# early and runs at the same rate.
#
# Let me verify: the backlog at any time t = results_produced(t) - results_transmitted(t)
# Results start at pixel 66. After that, 1 result per pixel (except row boundaries).
# TX starts when first result is available.
# 
# At pixel N (N>=66): results_produced = N-65 (roughly, for the 30-result rows)
# TX transmits at same rate, starting from pixel 66.
# So backlog = 0 or 1 at most!
#
# The ONLY time there's a backlog of >1 is if TX has startup latency.
# TX startup: result available -> tx_start pulse -> wait for baud_tick -> START bit
# The wait for baud_tick can be up to 434 clocks. But the next pixel comes 4340 clocks later.
# So TX has 4340 clocks to start and it only needs at most 434 to start. 
# TX frame = 10*434 = 4340 clocks. Next result in 4340 clocks. So TX just barely keeps up.
#
# Actually, there's a critical detail: TX takes EXACTLY 10 baud periods = 4340 clocks.
# But the TX might not start exactly on a baud tick. If tx_start comes just after
# a baud_tick, it waits up to 434 clocks for the next one. Then the frame takes
# 10*434 = 4340 clocks. Total = up to 434 + 4340 = 4774 clocks.
# But the next result comes in 4340 clocks. So there's a potential 434-clock overrun.
#
# Over 900 results, this could accumulate. But actually, after the first frame,
# TX's baud divider is synchronized - each frame takes exactly 10*434 = 4340 clocks
# from start to tx_done. And the next tx_start can only happen after tx_done.
# 
# So the real question: can TX fall behind by more than 1 entry?
# 
# Let me simulate the timing precisely.

BAUD_DIV = 434
FRAME = 10 * BAUD_DIV  # 4340 clocks per byte

# Track when each result is produced (in clock cycles from start)
# and when each can be transmitted

# Results are produced at pixel indices: row>=2 && col>=2
# pixel index p -> row = p//32, col = p%32
# result produced at clock = p * FRAME (when rx_valid fires)

result_times = []
for p in range(1024):
    row = p // 32
    col = p % 32
    if row >= 2 and col >= 2:
        result_times.append(p * FRAME)

print(f"Total results: {len(result_times)}")
print(f"First result at clock: {result_times[0]}")
print(f"Last result at clock: {result_times[-1]}")

# TX timing: TX can start a new frame only when idle (after tx_done of previous)
# First TX starts at result_times[0] + small latency (wait for baud_tick, max 434)
# Each TX frame takes exactly 10*434 = 4340 clocks
# But there's the initial baud_tick wait

# Simulate: TX starts at first result time + worst-case baud wait
# After that, each frame takes 4340 clocks, but tx_start must wait for tx_done

# Let's track the backlog with a single-entry buffer
# result_available_time[i] = result_times[i]
# tx_done_time[i] = time when TX finishes frame i

# With single entry: 
# tx_start_time[0] = result_times[0] (approximately, +0 to 434 for baud wait)
# tx_done_time[0] = tx_start_time[0] + 4340 (10 baud periods from start bit)
# tx_start_time[i] = max(result_times[i], tx_done_time[i-1])

# But the baud_tick alignment matters. Let's be pessimistic: 
# tx_start is latched, but actual frame begins at next baud_tick.
# Worst case: tx_start arrives 1 cycle after baud_tick -> wait 433 cycles.
# But after the first frame, subsequent frames: tx_done fires on a baud_tick,
# and the next tx_start can be latched immediately. The IDLE state checks
# start_req on the next baud_tick. So there's up to 434 cycle gap between
# tx_done and the actual start of the next frame.

# Let's model: each TX frame takes 4340 clocks for the bits, plus up to 434 
# for the gap waiting for baud_tick in IDLE. Worst case 4774 per frame.
# But actually, tx_done fires AT the baud_tick when STOP ends.
# Then IDLE: on next baud_tick, if start_req, begin START.
# So the gap is exactly 0 to 434 clocks.

# Pessimistic: gap = 434 every time
# tx_time[i] = max(result_times[i], tx_done[i-1]) + 434 (wait) + 4340 (frame)
# But this is too pessimistic. Let's just check if backlog ever exceeds 1.

backlog = 0
max_backlog = 0
tx_free_at = 0  # when TX is free to accept new frame

for i, rt in enumerate(result_times):
    # Result produced at rt
    # If TX is free (tx_free_at <= rt), we can start immediately
    # TX frame takes 4340 + up to 434 wait = 4774 worst case
    if tx_free_at <= rt:
        # TX was idle, start now
        # Wait for baud_tick (0 to 434) + frame (4340)
        tx_free_at = rt + 434 + 4340  # worst case
        backlog = 0  # result consumed immediately
    else:
        # TX is busy, result must wait in buffer
        backlog += 1
        # It will be transmitted when TX is free
        tx_free_at = tx_free_at + 434 + 4340  # next frame
        backlog -= 1  # consumed
    max_backlog = max(max_backlog, backlog)

print(f"\nWorst case (434 wait every frame):")
print(f"Max backlog: {max_backlog}")

# More realistic: after first frame, the baud_tick alignment is fixed
# tx_done fires on baud_tick. Next baud_tick is 434 later.
# If start_req is set immediately after tx_done, it starts on next baud_tick.
# So gap = 434 clocks consistently.
# Frame = 10*434 = 4340. Total per frame = 434 + 4340 = 4774.
# But results come every 4340 clocks. So TX is SLOWER by 434 per frame!
# Over 900 frames: 900 * 434 = 390,600 clocks behind.
# That's 390600/4340 = 90 frames behind! That matches the comment in the code.

# But wait - is the gap really 434 every time? Let's look at the TX FSM more carefully.
# tx_done fires at baud_tick in STOP state. State goes to IDLE.
# In IDLE, on next baud_tick, if start_req, go to START.
# So there's ALWAYS exactly 1 baud period (434 clocks) between frames.
# 
# Hmm, but that means TX takes 11 baud periods per byte, not 10!
# 11 * 434 = 4774 clocks per result.
# Results come every 4340 clocks.
# Backlog grows by (4774-4340)/4340 = 0.31 per result.
# Over 900 results: 900 * 0.31 = 279... but that's more than 128!
#
# Wait, let me re-examine. The TX FSM:
# IDLE -> (baud_tick, start_req) -> START (start bit, 1 baud)
# START -> (baud_tick) -> DATA bit0 (1 baud)
# DATA -> (baud_tick) -> DATA bit1..7 (7 more baud)
# DATA bit7 -> (baud_tick) -> STOP (1 baud)
# STOP -> (baud_tick) -> IDLE, tx_done=1
# IDLE -> (baud_tick, start_req) -> START
#
# So: START(1) + DATA(8) + STOP(1) = 10 baud periods for the frame.
# Then 1 baud period in IDLE before next START.
# Total = 11 baud periods = 11*434 = 4774 clocks.
#
# BUT: the result is produced when rx_valid fires, which is at the END
# of the RX frame (after the 8th data bit, at the baud_tick).
# The RX frame also takes 10 baud periods (start + 8 data + stop).
# Actually, looking at uart_rx: it goes STOP -> DATA(8 bits) -> STOP
# The STOP state detects start bit. Then DATA samples 8 bits.
# After bit 7, rx_valid fires and state goes to STOP.
# So RX takes: 1 (detect start) + 8 (data) = 9 baud periods to produce rx_valid.
# Then it's in STOP, waiting for next start bit.
# The stop bit of the incoming frame is 1 baud period.
# So between rx_valid pulses: 10 baud periods (full frame).
#
# So RX produces every 4340 clocks, TX consumes every 4774 clocks.
# Backlog grows! This is why the FIFO was needed.
#
# BUT WAIT - can we eliminate the IDLE gap? If tx_start is asserted
# BEFORE tx_done fires (i.e., start_req is latched while TX is busy),
# then when TX enters IDLE, start_req is already 1, and on the VERY NEXT
# baud_tick it starts. That's still 1 baud period gap.
#
# Actually, can we start the next frame IMMEDIATELY after STOP?
# In the STOP state, at baud_tick: tx_done=1, state->IDLE.
# On the SAME baud_tick in IDLE: we check start_req. But state just
# changed to IDLE this cycle, so the IDLE case runs NEXT baud_tick.
# So yes, 1 baud gap minimum.
#
# UNLESS we restructure: in STOP state, if start_req, go directly to START
# instead of IDLE. That eliminates the gap! Back-to-back frames.
# Then TX takes exactly 10 baud periods = 4340 clocks = same as RX.
# Backlog = 0 or 1!

print("\n--- If we eliminate the IDLE gap (STOP->START directly) ---")
print("TX takes 10 baud periods = 4340 clocks = same as RX")
print("Backlog would be at most 1 (single holding register)")

# Let's verify with the STOP->START optimization
backlog = 0
max_backlog = 0
tx_free_at = 0

for i, rt in enumerate(result_times):
    if tx_free_at <= rt:
        tx_free_at = rt + 4340  # 10 baud, no gap
        backlog = 0
    else:
        backlog += 1
        tx_free_at = tx_free_at + 4340
        backlog -= 1
    max_backlog = max(max_backlog, backlog)

print(f"Max backlog with no-gap TX: {max_backlog}")

# But there's still the initial latency: first result at pixel 66.
# TX starts at that point. But the baud_tick might not be aligned.
# Worst case: 434 clock wait for first baud_tick.
# That's less than 1 frame, so backlog stays at 1.

# Let's also check with the 434 initial wait
backlog = 0
max_backlog = 0
tx_free_at = 0

for i, rt in enumerate(result_times):
    if i == 0:
        tx_free_at = rt + 434 + 4340  # initial wait + frame
    elif tx_free_at <= rt:
        tx_free_at = rt + 4340
        backlog = 0
    else:
        backlog += 1
        tx_free_at = tx_free_at + 4340
        backlog -= 1
    max_backlog = max(max_backlog, backlog)

print(f"Max backlog with initial wait + no-gap TX: {max_backlog}")