# The first simulation (with drops) was a different, buggy model.
# The event-driven simulation shows max backlog = 1 for both TX variants.
# 
# But wait - the first model showed drops starting at result 767. That model
# was wrong because it didn't properly handle the TX taking the buffered result.
# The event-driven model is correct and shows max backlog = 1.
#
# Let me verify the event-driven model is correct by tracing a few steps.

BAUD_DIV = 434

def next_baud_tick(t):
    k = (t - 433 + 434 - 1) // 434
    if k < 0: k = 0
    bt = k * 434 + 433
    if bt < t: bt = (k+1) * 434 + 433
    return bt

result_pixels = []
for p in range(1024):
    row = p // 32
    col = p % 32
    if row >= 2 and col >= 2:
        result_pixels.append(p)
result_times = [p * 4340 for p in result_pixels]

# Trace with 11-baud cycle
buffer_count = 0
max_backlog = 0
tx_busy_until = 0

trace = []
for i, rt in enumerate(result_times):
    if rt >= tx_busy_until:
        bt = next_baud_tick(rt)
        tx_busy_until = bt + 11 * BAUD_DIV
        old_buf = buffer_count
        buffer_count = 0
        if i < 5 or (i > 28 and i < 35):
            trace.append(f"result {i:3d} at {rt:7d}: TX FREE, bt={bt:7d}, busy_until={tx_busy_until:7d}, buf {old_buf}->0")
    else:
        buffer_count += 1
        if buffer_count > max_backlog:
            max_backlog = buffer_count
        tx_busy_until = tx_busy_until + 11 * BAUD_DIV
        old_buf = buffer_count
        buffer_count -= 1
        if i < 5 or (i > 28 and i < 35):
            trace.append(f"result {i:3d} at {rt:7d}: TX BUSY, busy_until={tx_busy_until:7d}, buf {old_buf}->{buffer_count}")

for t in trace:
    print(t)
print(f"\nMax backlog: {max_backlog}")

# Let me also check: what if the initial baud_tick wait is very unlucky?
# The first result is at time 286440.
# 286440 / 434 = 660.0 exactly. So 286440 = 660 * 434.
# baud_tick at 660*434 + 433 = 286440 + 433 = 286873.
# Wait, that's 433 cycles later. But 286440 is a multiple of 434.
# baud_ticks are at 433, 867, ... = k*434 + 433.
# 286440 = 660*434. So the baud_tick just before is at 659*434+433 = 286006+433=286439.
# The next baud_tick is at 660*434+433 = 286873.
# So wait = 286873 - 286440 = 433. That's almost 1 full baud period!
#
# After that, TX cycle = 11*434 = 4774.
# tx_busy_until = 286873 + 4774 = 291647.
# Next result at 290780. 290780 < 291647, so TX is busy.
# buffer = 1, tx_busy_until = 291647 + 4774 = 296421.
# Next result at 295120. 295120 < 296421, TX busy.
# buffer = 1, tx_busy_until = 296421 + 4774 = 301195.
# ...
# This continues. Let me see when TX catches up.

# After how many results does TX catch up?
# TX cycle = 4774, result interval = 4340.
# TX falls behind by 434 per result.
# After N results: behind by N*434.
# TX catches up when result interval has a gap (row boundary).
# Row boundary: 3 result intervals = 3*4340 = 13020 clocks gap.
# In 13020 clocks, TX does 13020/4774 = 2.7 frames.
# But only 1 result arrives in that gap. So TX catches up by 1.7 frames.
# 
# Per row (30 results): TX falls behind by 30*434 = 13020 clocks = 3 frames.
# Row boundary: TX catches up by 1.7 frames.
# Net per row: 3 - 1.7 = 1.3 frames behind. GROWING!
#
# But my simulation shows max backlog = 1. Let me check if I have a bug.

# Let me trace more carefully around a row boundary
# Row 2: results 0-29 (pixels 66-95)
# Row 3: results 30-59 (pixels 98-127)
# Gap: result 29 at pixel 95, result 30 at pixel 98. 
# Time gap = (98-95)*4340 = 13020 clocks.

print("\n--- Around first row boundary (results 28-32) ---")
buffer_count = 0
max_backlog = 0
tx_busy_until = 0

for i, rt in enumerate(result_times):
    if rt >= tx_busy_until:
        bt = next_baud_tick(rt)
        tx_busy_until = bt + 11 * BAUD_DIV
        buffer_count = 0
        if 28 <= i <= 35:
            print(f"result {i:3d} pixel {result_pixels[i]:4d} at {rt:7d}: TX FREE, bt={bt:7d}, busy_until={tx_busy_until:7d}, buf=0")
    else:
        buffer_count += 1
        if buffer_count > max_backlog:
            max_backlog = buffer_count
        tx_busy_until = tx_busy_until + 11 * BAUD_DIV
        old_buf = buffer_count
        buffer_count -= 1
        if 28 <= i <= 35:
            print(f"result {i:3d} pixel {result_pixels[i]:4d} at {rt:7d}: TX BUSY, busy_until={tx_busy_until:7d}, buf={old_buf}->{buffer_count}")

print(f"Max backlog: {max_backlog}")