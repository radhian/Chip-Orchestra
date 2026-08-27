# Hmm, max backlog is 0 in all cases? Let me check more carefully.
# The issue might be that my model is too optimistic. Let me trace through
# the first few results manually.

BAUD_DIV = 434
FRAME = 10 * BAUD_DIV  # 4340

# Results produced at these pixel indices (row>=2, col>=2)
result_pixels = []
for p in range(1024):
    row = p // 32
    col = p % 32
    if row >= 2 and col >= 2:
        result_pixels.append(p)

print(f"First 10 result pixels: {result_pixels[:10]}")
print(f"Gaps between first 10: {[result_pixels[i+1]-result_pixels[i] for i in range(9)]}")

# So results come at pixels: 66, 67, 68, ..., 31 (end of row 2)
# Then 98, 99, ... (row 3, col 2..31)
# Gap at row boundary: pixel 31 (row 2, col 31) -> pixel 64 (row 3, col 0) -> 65 -> 66
# Wait, row 2 = pixels 64-95. col 2 = pixel 66. col 31 = pixel 95.
# Row 3 = pixels 96-127. col 2 = pixel 98.
# So gap from pixel 95 to 98 = 3 pixels = 3*4340 = 13020 clocks.

# Let me trace the timing with the CURRENT TX (11 baud = 4774 per frame)
# and see the actual backlog

result_times = [p * FRAME for p in result_pixels]

# Current TX: 11 baud per frame = 4774 clocks
# But actually, let me be more precise about the TX timing.
# 
# The TX FSM: IDLE -> START -> DATA(8 bits) -> STOP -> IDLE
# Each state lasts 1 baud period (434 clocks).
# STOP -> IDLE: at baud_tick, tx_done=1, state=IDLE
# IDLE -> START: at NEXT baud_tick (434 clocks later), if start_req
# 
# So from tx_done to next frame start = 434 clocks (1 baud in IDLE).
# From frame start to tx_done = 10*434 = 4340 clocks.
# Total cycle = 434 + 4340 = 4774 clocks.
#
# But wait - start_req is latched on ANY clock, not just baud_tick.
# So if tx_start is asserted during STOP or DATA, start_req=1.
# When we enter IDLE, on the next baud_tick, we see start_req=1 and start.
# So the IDLE period is exactly 1 baud (434 clocks).
#
# UNLESS tx_start is asserted DURING the IDLE period itself.
# If tx_start comes after IDLE starts but before the baud_tick,
# start_req is set, and on the baud_tick, we start. Still 1 baud.
# If tx_start comes just after the baud_tick in IDLE, we wait until
# the NEXT baud_tick. That's 2 baud in IDLE! But this only happens
# if the result arrives during IDLE, which means TX was idle.
# In that case there's no backlog anyway.

# So for back-to-back frames: 4774 clocks per frame.
# Let me trace the backlog precisely.

TX_PERIOD = 11 * BAUD_DIV  # 4774

# First result at result_times[0] = 66 * 4340 = 286440
# TX starts: result_times[0] + delay (0 to 434)
# Let's use worst case delay = 434

delay = 434
tx_free_at = result_times[0] + delay  # when TX can start first frame
# First frame done at tx_free_at + 4340 (10 baud for the frame itself)
tx_done_at = tx_free_at + 10 * BAUD_DIV  # 4340

backlog = 1  # first result is being transmitted
max_backlog = 1

for i in range(1, len(result_times)):
    rt = result_times[i]
    if rt >= tx_done_at + BAUD_DIV:  # TX done + 1 baud IDLE = free
        # TX is free, start new frame
        # But there might be a wait for baud_tick
        # In the worst case, result arrives just after baud_tick in IDLE
        # Actually, if TX is free and result arrives, start_req is latched,
        # and on next baud_tick, frame starts. Wait = 0 to 434.
        tx_done_at = rt + BAUD_DIV + 10 * BAUD_DIV  # 1 baud wait + 10 baud frame
        backlog = 1
    else:
        # TX is busy, result waits in buffer
        backlog += 1
        # This result will be transmitted after current frame + 1 baud IDLE
        tx_done_at = tx_done_at + BAUD_DIV + 10 * BAUD_DIV  # 4774
        backlog -= 1  # now being transmitted
    max_backlog = max(max_backlog, backlog)

print(f"Max backlog (current TX, 11 baud/frame): {max_backlog}")
print(f"Backlog trace (first 50):")

# Redo with trace
delay = 434
tx_free_at = result_times[0] + delay
tx_done_at = tx_free_at + 10 * BAUD_DIV
backlog = 1
max_backlog = 1
trace = []

for i in range(1, min(50, len(result_times))):
    rt = result_times[i]
    if rt >= tx_done_at + BAUD_DIV:
        tx_done_at = rt + BAUD_DIV + 10 * BAUD_DIV
        backlog = 1
        trace.append(f"  result {i} at {rt}: TX free, backlog=1")
    else:
        backlog += 1
        tx_done_at = tx_done_at + BAUD_DIV + 10 * BAUD_DIV
        backlog -= 1
        trace.append(f"  result {i} at {rt}: TX busy, backlog={backlog+1}->{backlog}")
    max_backlog = max(max_backlog, backlog)

for t in trace[:30]:
    print(t)