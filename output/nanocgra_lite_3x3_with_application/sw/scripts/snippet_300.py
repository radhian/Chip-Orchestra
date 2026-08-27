# Interesting! The max backlog is only 1, not 90 as the comment claimed.
# The row boundary gaps (2 pixels = 8680 clocks) allow TX to catch up.
# 
# Let me verify: within a row, 30 results come 4340 clocks apart.
# TX takes 4774 clocks per frame. So TX falls behind by 434 clocks per frame.
# After 30 frames: 30*434 = 13020 clocks behind.
# But the row boundary gap is 3*4340 = 13020 clocks (pixels 95->98).
# So TX catches up exactly! Backlog stays at 1.
#
# So even with the current 11-baud TX, the max backlog is 1!
# A single-entry holding register is sufficient.
#
# But wait - my model might be wrong. Let me check if the row boundary
# gap is really 3 pixels. 
# Row 2: pixels 64-95. Results at col 2..31 = pixels 66..95 = 30 results.
# Row 3: pixels 96-127. Results at col 2..31 = pixels 98..127 = 30 results.
# Gap: pixel 95 (last result of row 2) to pixel 98 (first result of row 3) = 3 pixels.
# 3 * 4340 = 13020 clocks. TX needs 4774 per frame.
# In 13020 clocks, TX can do 13020/4774 = 2.7 frames.
# But there's only 1 result waiting (the one at pixel 98).
# So TX catches up and the backlog drops to 0 or stays at 1.
#
# Let me verify the full simulation with precise timing.

BAUD_DIV = 434
FRAME = 10 * BAUD_DIV  # 4340

result_pixels = []
for p in range(1024):
    row = p // 32
    col = p % 32
    if row >= 2 and col >= 2:
        result_pixels.append(p)

result_times = [p * FRAME for p in result_pixels]

# Current TX: 11 baud per frame = 4774
# But let me be even more precise. The TX has its own baud_gen.
# The TX baud_cnt free-runs. When tx_start is latched (start_req=1),
# the frame starts at the NEXT baud_tick.
# 
# The first tx_start comes when the first result is produced (pixel 66).
# At that point, the TX baud_cnt is at some arbitrary phase.
# Worst case: baud_cnt just rolled to 0, so we wait 433 cycles.
# 
# After the first frame, tx_done fires at a baud_tick.
# Then IDLE for 1 baud (434 cycles), then START.
# So from first tx_start to first tx_done = 10*434 = 4340.
# From tx_done to next tx_start = 434 (IDLE).
# From tx_start to tx_done = 4340.
# Cycle = 4774.
#
# But the KEY question: does the result arrive during IDLE or during a frame?
# If during IDLE: start_req is set, and on the next baud_tick, frame starts.
#   The wait is 0 to 434. But since we're in IDLE and the result arrives
#   at a specific time, the wait depends on alignment.
# If during a frame: start_req is set, and when STOP->IDLE->next baud_tick,
#   frame starts. The result waits in the buffer.
#
# Let me just simulate with the worst case and see if backlog ever exceeds 1.

# More precise model:
# TX state machine cycles: IDLE(wait for start_req) -> START(434) -> DATA(8*434) -> STOP(434) -> IDLE
# When start_req is set, on next baud_tick in IDLE, go to START.
# 
# The first frame: start_req set at time T0 = result_times[0].
# TX is in IDLE. Next baud_tick at T0 + (434 - (T0 % 434)).
# Frame: START(434) + DATA(8*434) + STOP(434) = 4340.
# tx_done at T0 + wait + 4340.
# Then IDLE for 434, then next frame.
#
# For subsequent frames: if start_req was set during the frame,
# then at the baud_tick after STOP (i.e., in IDLE), we start.
# IDLE lasts exactly 1 baud (434). So cycle = 4774.
#
# If start_req is NOT set when we enter IDLE (no result waiting),
# we stay in IDLE until start_req is set. Then next baud_tick.

# Let me simulate with a state machine
tx_baud_phase = 0  # TX baud counter phase (free-running)
tx_state = "IDLE"
tx_state_end = 0  # when current state ends
tx_bit = 0
start_req = 0
tx_done_time = -1

# Results queue
backlog = 0
max_backlog = 0

# Event-driven simulation
events = []  # (time, type)
for i, rt in enumerate(result_times):
    events.append((rt, f"result_{i}"))

# Sort events
events.sort()

# TX simulation
tx_free_at = 0  # when TX will be free to start a new frame
current_frame_end = 0  # when current frame's tx_done will fire

ei = 0
for time, etype in events:
    if etype.startswith("result"):
        # A result is produced
        if time >= current_frame_end + BAUD_DIV:
            # TX is free (frame done + IDLE period passed)
            # Start new frame: wait for baud_tick (0 to 434)
            wait = BAUD_DIV - (time % BAUD_DIV) if (time % BAUD_DIV) != 0 else 0
            current_frame_end = time + wait + 10 * BAUD_DIV
            backlog = 1  # this result is being transmitted
        else:
            # TX is busy
            backlog += 1
            # This result will be transmitted after current frame + IDLE
            current_frame_end = current_frame_end + BAUD_DIV + 10 * BAUD_DIV
            backlog -= 1
        max_backlog = max(max_backlog, backlog)

print(f"Max backlog (precise model, current TX): {max_backlog}")

# Now with no-gap TX (STOP->START directly, 10 baud per frame)
backlog = 0
max_backlog = 0
current_frame_end = 0

for i, rt in enumerate(result_times):
    if i == 0:
        wait = BAUD_DIV - (rt % BAUD_DIV) if (rt % BAUD_DIV) != 0 else 0
        current_frame_end = rt + wait + 10 * BAUD_DIV
        backlog = 1
    else:
        if rt >= current_frame_end:
            # TX is free
            wait = BAUD_DIV - (rt % BAUD_DIV) if (rt % BAUD_DIV) != 0 else 0
            current_frame_end = rt + wait + 10 * BAUD_DIV
            backlog = 1
        else:
            backlog += 1
            current_frame_end = current_frame_end + 10 * BAUD_DIV
            backlog -= 1
        max_backlog = max(max_backlog, backlog)

print(f"Max backlog (no-gap TX): {max_backlog}")