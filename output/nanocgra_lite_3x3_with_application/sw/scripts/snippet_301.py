# Great! Max backlog is 1 in both cases. The row boundary gaps give enough
# catch-up time. So a single-entry holding register is sufficient.
#
# But I need to be careful: my model assumes the worst-case baud_tick wait
# only happens on the FIRST frame. After that, the TX baud_tick is 
# synchronized to the frame boundaries. Let me verify this is correct.
#
# Actually, the TX has its OWN baud_gen (free-running). The TX FSM transitions
# on baud_ticks. So:
# - Frame starts at baud_tick T
# - START bit: T to T+434 (next baud_tick)
# - DATA bit 0: T+434 to T+868
# - ...
# - DATA bit 7: T+3472 to T+3906
# - STOP: T+3906 to T+4340
# - At T+4340 (baud_tick): tx_done, state->IDLE
# - IDLE: T+4340 to T+4774 (next baud_tick)
# - At T+4774 (baud_tick): if start_req, state->START
#
# So frames are aligned to baud_ticks. The cycle is 4774 = 11*434.
# Results arrive at times that are multiples of 4340 = 10*434.
# The TX cycle is 4774 = 11*434.
# 
# LCM(4340, 4774) = LCM(10*434, 11*434) = 434 * LCM(10,11) = 434 * 110 = 47740
# So the phase difference cycles every 47740/4340 = 11 results.
# 
# In 11 results: TX takes 11*4774 = 52514 clocks. RX produces 11 in 11*4340 = 47740.
# TX falls behind by 52514-47740 = 4774 = 1 frame. So after 11 results, backlog = 1.
# But row boundary happens every 30 results. 30/11 = 2.7 cycles.
# After 30 results: backlog = 30 * (4774-4340)/4340 = 30 * 0.1 = 3.
# But row boundary gives 3*4340 = 13020 clocks = 13020/4774 = 2.7 frames catch-up.
# Net: 3 - 2.7 = 0.3. So backlog grows by 0.3 per row.
# Over 30 rows: 9. That's more than 1!
#
# Wait, that contradicts my simulation. Let me recheck.
# The issue is that my simulation model might be wrong.
# Let me trace more carefully.

BAUD_DIV = 434

# Let me do a clock-by-clock simulation of the TX state machine
# and track the backlog precisely.

result_pixels = []
for p in range(1024):
    row = p // 32
    col = p % 32
    if row >= 2 and col >= 2:
        result_pixels.append(p)

# Each pixel takes 10*BAUD_DIV = 4340 clocks (UART frame)
# rx_valid fires at the end of the 8th data bit = 9*BAUD_DIV after start
# But for simplicity, let's say rx_valid fires at p * 10 * BAUD_DIV
# (aligned to the start of the frame, approximately)

# Actually, let me be precise. The testbench sends:
# start bit (434 clocks) + 8 data (8*434) + stop (434) = 4340 clocks
# The RX detects start at some baud_tick, then samples 8 bits.
# rx_valid fires at the 8th data bit's baud_tick.
# So rx_valid is at approximately frame_start + 9*434 = frame_start + 3906.
# But the frame_start is when the testbench drives data_i=0.
# The RX detects it at the next baud_tick after the falling edge.
# 
# For simplicity, let's model rx_valid at p * 4340 + 3906 (9 baud into frame).
# But the exact phase doesn't matter much for backlog analysis.
# Let me just use p * 4340.

result_times = [p * 4340 for p in result_pixels]

# TX state machine simulation
# States: IDLE, START, DATA0..DATA7, STOP
# Each state lasts BAUD_DIV clocks (one baud period)
# Transitions on baud_tick

# TX baud_gen: free-running, baud_tick every 434 clocks, starting from reset.
# So baud_ticks at: 433, 867, 1301, ... (i.e., at (n+1)*434 - 1)
# Actually, baud_gen: cnt counts 0..433, baud_tick=1 when cnt==433.
# So baud_tick at clocks 433, 867, 1301, ... = n*434 + 433

# Let me simulate clock by clock (but that's 4.4M clocks, too slow)
# Instead, event-driven:

# TX state: (state_name, state_start_time, state_end_time)
# state_end_time = state_start_time + BAUD_DIV (aligned to baud_tick)

# The TX baud_tick happens at times: 433, 867, 1301, ... = k*434 + 433 for k=0,1,2,...
# But after reset, the baud_gen starts counting from 0.
# So baud_ticks at: 433, 867, 1301, ...

# Let me find the first baud_tick >= some time t
def next_baud_tick(t):
    """Return the first baud_tick time >= t. Baud ticks at k*434+433."""
    k = (t - 433 + 434 - 1) // 434  # ceiling division
    if k < 0:
        k = 0
    bt = k * 434 + 433
    if bt < t:
        bt = (k+1) * 434 + 433
    return bt

# Test
print(f"next_baud_tick(0) = {next_baud_tick(0)}")  # 433
print(f"next_baud_tick(433) = {next_baud_tick(433)}")  # 433
print(f"next_baud_tick(434) = {next_baud_tick(434)}")  # 867
print(f"next_baud_tick(866) = {next_baud_tick(866)}")  # 867
print(f"next_baud_tick(867) = {next_baud_tick(867)}")  # 867

# TX FSM simulation (event-driven)
# State: IDLE -> START -> DATA(8) -> STOP -> IDLE
# In IDLE: on baud_tick, if start_req, go to START
# In START: on baud_tick, go to DATA0, output bit 0
# In DATAi: on baud_tick, output bit i+1 (or go to STOP if i==7)
# In STOP: on baud_tick, tx_done=1, go to IDLE

# start_req is latched on ANY clock when tx_start is asserted

# The controller asserts tx_start when it pops a result from the buffer.
# With a single-entry buffer:
# - When a result is produced and buffer is empty: store it
# - When TX is in IDLE and buffer is full: assert tx_start, clear buffer
# - When a result is produced and buffer is full: it's dropped! (BAD)
#   OR: we need to ensure this never happens (backlog <= 1)

# Let me simulate the TX with a single-entry buffer and see if any result is dropped.

tx_state = "IDLE"
tx_state_until = 0  # baud_tick time when current state ends
start_req = 0
tx_done_time = -1

buffer_full = 0
buffer_data = 0
results_txed = 0
results_dropped = 0
max_backlog = 0

# Process results in time order
for i, rt in enumerate(result_times):
    # At time rt, a result is produced
    if not buffer_full:
        buffer_full = 1
        buffer_data = i
    else:
        # Buffer is full! Check if TX can accept it
        # TX can accept if start_req is not set and TX is in IDLE
        # But start_req might already be set from a previous result
        # If TX is currently transmitting, the result is lost
        results_dropped += 1
        print(f"DROP at result {i} (pixel {result_pixels[i]}) time {rt}")
    
    # Now check: can TX start?
    # TX starts when in IDLE and start_req is set (on baud_tick)
    # The controller sets tx_start when buffer is full and TX is in IDLE
    # But in our model, the controller pops the buffer when TX is in IDLE
    
    # Actually, let me model it differently:
    # The controller has a single-entry buffer.
    # When TX is in IDLE (tx_done was received), if buffer is full,
    # assert tx_start with buffer data, clear buffer.
    # TX latches start_req and starts on next baud_tick.
    
    # So the flow is:
    # 1. Result produced -> stored in buffer
    # 2. If TX is idle -> tx_start asserted -> buffer cleared
    # 3. TX starts frame on next baud_tick
    # 4. tx_done fires at end of frame -> TX is idle again
    # 5. If buffer has a new result by then -> tx_start again
    
    # The question: between tx_done and the next result, is the buffer empty?
    # If yes, TX waits in IDLE. If no, TX starts immediately.
    
    # Let me track when TX is ready to accept a new frame
    pass

# This is getting complex. Let me just do a proper event-driven simulation.
print("\n--- Event-driven simulation ---")

# Events: result produced, tx_done
# State: buffer (0 or 1 entry), TX state (IDLE/BUSY), start_req (0/1)

events = []
for i, rt in enumerate(result_times):
    events.append((rt, 'result', i))
events.sort()

buffer_count = 0
tx_busy = False  # TX is transmitting
tx_done_at = 0  # when TX will finish (tx_done fires)
start_req = False
max_backlog = 0
results_txed = 0
drops = 0

# Process events in order
# When a result arrives:
#   - If TX is not busy and no start_req: set start_req, TX will start on next baud_tick
#   - If TX is busy or start_req: store in buffer (if space)
#   - If buffer full: DROP (or backlog > 1)
#
# When tx_done fires:
#   - TX becomes idle
#   - If buffer has data: set start_req, clear buffer
#   - TX starts on next baud_tick
#
# When TX starts (start_req + baud_tick in IDLE):
#   - TX becomes busy, start_req cleared
#   - tx_done will fire at start_time + 10*BAUD_DIV

# But I need to track baud_ticks for the TX start timing.
# Let me simplify: when start_req is set and TX is idle,
# the frame starts at the next baud_tick.
# Frame duration = 10*BAUD_DIV (START+8DATA+STOP).
# Then 1 baud in IDLE, then next frame if start_req.

# Actually, the simplest model:
# - TX cycle = 11*BAUD_DIV (10 baud frame + 1 baud IDLE) when back-to-back
# - TX cycle = 10*BAUD_DIV + wait when starting from idle

# Let me track: tx_ready_at = when TX can start a new frame
# (either it was idle, or just finished + IDLE period)

tx_ready_at = 0  # TX is ready to start a new frame at this time
# When a frame starts at time t:
#   tx_done_at = t + 10*BAUD_DIV
#   tx_ready_at = tx_done_at + BAUD_DIV (IDLE period)

# But if TX is idle and a result arrives, the frame starts at next baud_tick
# after tx_start is asserted.

# Let me just track the backlog (buffer count) and see if it exceeds 1.

buffer_count = 0
max_backlog = 0
# tx_busy_until: time when TX finishes current frame (including IDLE gap)
tx_busy_until = 0  # TX is free at this time
# When TX is free and buffer has data, it starts a frame.
# Frame start: next baud_tick after buffer gets data (or immediately if aligned)
# Frame + IDLE = 11*BAUD_DIV

ei = 0
for i, rt in enumerate(result_times):
    # Result arrives at rt
    if rt >= tx_busy_until:
        # TX is free
        buffer_count = 1  # result goes to buffer, then immediately to TX
        # TX starts at next baud_tick
        bt = next_baud_tick(rt)
        # Frame + IDLE = 11*BAUD_DIV
        tx_busy_until = bt + 11 * BAUD_DIV
        buffer_count = 0  # TX took it
    else:
        # TX is busy
        buffer_count += 1
        if buffer_count > max_backlog:
            max_backlog = buffer_count
        # TX will take this when it's free
        tx_busy_until = tx_busy_until + 11 * BAUD_DIV  # next frame cycle
        buffer_count -= 1  # TX took it
    
print(f"Max backlog (current TX, 11 baud cycle): {max_backlog}")

# With no-gap TX (10 baud cycle)
buffer_count = 0
max_backlog = 0
tx_busy_until = 0

for i, rt in enumerate(result_times):
    if rt >= tx_busy_until:
        buffer_count = 1
        bt = next_baud_tick(rt)
        tx_busy_until = bt + 10 * BAUD_DIV
        buffer_count = 0
    else:
        buffer_count += 1
        if buffer_count > max_backlog:
            max_backlog = buffer_count
        tx_busy_until = tx_busy_until + 10 * BAUD_DIV
        buffer_count -= 1

print(f"Max backlog (no-gap TX, 10 baud cycle): {max_backlog}")