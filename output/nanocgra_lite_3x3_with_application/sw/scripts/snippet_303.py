# I see - the backlog never exceeds 1 because:
# 1. When TX is busy and a result arrives, buffer goes to 1, then immediately
#    TX takes it (buffer back to 0), and tx_busy_until extends by 4774.
# 2. So the buffer is always 0 or 1.
#
# But this model assumes TX can always extend its busy time. That's correct -
# TX processes results back-to-back. The "backlog" in my model is just whether
# the result had to wait (buffer=1 momentarily) or not.
#
# The real question is: does tx_busy_until grow faster than result_times?
# If tx_busy_until > result_times[i] for all i, then TX is always behind.
# But the row boundary gaps allow TX to catch up.
#
# Let me check: does tx_busy_until ever fall below result_times[i]?
# i.e., does TX ever become FREE (not just for the first frame)?

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

buffer_count = 0
max_backlog = 0
tx_busy_until = 0
tx_free_count = 0

for i, rt in enumerate(result_times):
    if rt >= tx_busy_until:
        bt = next_baud_tick(rt)
        tx_busy_until = bt + 11 * BAUD_DIV
        buffer_count = 0
        tx_free_count += 1
    else:
        buffer_count += 1
        if buffer_count > max_backlog:
            max_backlog = buffer_count
        tx_busy_until = tx_busy_until + 11 * BAUD_DIV
        buffer_count -= 1

print(f"Total results: {len(result_times)}")
print(f"TX free count (TX was idle when result arrived): {tx_free_count}")
print(f"Max backlog: {max_backlog}")
print(f"Final tx_busy_until: {tx_busy_until}")
print(f"Last result time: {result_times[-1]}")
print(f"TX finishes at: {tx_busy_until}")
print(f"TX lag behind last result: {tx_busy_until - result_times[-1]}")

# So TX is always busy (never free except the first frame).
# The backlog is always 1 (each result waits for TX to finish the previous one).
# But TX never falls more than 1 behind because the row boundary gaps
# allow TX to catch up.
#
# Wait, but if TX is NEVER free (except first), that means TX is always behind.
# The backlog is 1 (the current result waits for the previous frame to finish).
# But it never grows to 2 because the row boundary gap allows TX to catch up
# to the point where the next result arrives just as TX finishes.
#
# Actually, let me check: is tx_busy_until always > result_times[i]?
# If so, TX is always behind by some amount. But the backlog is 1 because
# each result is taken by TX immediately when the previous frame finishes.
#
# The key insight: with a single-entry buffer, the controller:
# 1. Stores the result in the buffer when it's produced
# 2. When TX finishes (tx_done), pops the buffer and starts TX
# 3. If a new result arrives while TX is busy, it goes to the buffer
# 4. If the buffer is full when a result arrives... PROBLEM!
#
# But my simulation shows the buffer is always 0 when a new result arrives
# (because TX just took the previous one). So the buffer never overflows!
#
# Wait, that's not right. Let me re-examine. In my model:
# - When TX is busy and result arrives: buffer = 1, then TX extends, buffer = 0
# This means the result is immediately consumed by TX (which extends its busy time).
# But in reality, TX can't extend its busy time - it has to finish the current frame
# first, THEN start the next one. The buffer holds the result until TX is free.
#
# My model is actually correct: tx_busy_until += 4774 means the next frame will
# finish 4774 clocks later. The result waits in the buffer until then.
# The question is whether a SECOND result arrives before the first is taken from
# the buffer. That would mean buffer = 2.
#
# In my model, buffer goes to 1 then immediately back to 0 because I model
# TX as extending its busy time. But in reality, the buffer stays at 1 until
# tx_done fires. So I need to check if a second result arrives before tx_done.
#
# Let me model it properly: the buffer holds the result until tx_done,
# then TX starts the next frame.

# Proper model:
# - result arrives -> if buffer empty, store in buffer
# - tx_done fires -> if buffer full, start TX (tx_start), clear buffer
# - TX frame takes 10*BAUD_DIV + 1*BAUD_DIV IDLE = 11*BAUD_DIV
# - If buffer is full when result arrives -> OVERFLOW (need depth > 1)

# So the question is: between tx_done events, do 2 results ever arrive?
# tx_done period = 11*BAUD_DIV = 4774
# result interval = 4340 (within a row)
# 4774 > 4340, so YES, 2 results can arrive between tx_done events!
# But the first one goes to the buffer, and the second one finds the buffer full!
#
# Wait, no. Let me think again.
# tx_done fires at time T. Buffer is checked. If full, tx_start, buffer cleared.
# TX frame runs from T+wait to T+wait+4340. tx_done at T+wait+4340.
# Then IDLE for 434. Next tx_done at T+wait+4340+434 = T+wait+4774.
# 
# Results arrive at times R0, R1, R2, ...
# If R0 > T (TX was idle), buffer gets R0, tx_start at next baud_tick.
# tx_done at R0+wait+4340. Next check at R0+wait+4340.
# R1 arrives at R0+4340. Is R0+4340 < R0+wait+4340? Yes if wait > 0.
# So R1 arrives BEFORE tx_done. Buffer gets R1 (buffer was cleared when TX started).
# Wait, buffer is cleared when tx_start is asserted (at R0+wait).
# R1 arrives at R0+4340. tx_start was at R0+wait (wait < 434).
# So R0+4340 > R0+wait. Buffer is empty. R1 goes to buffer.
# tx_done at R0+wait+4340. R1 is in buffer. tx_start for R1.
# R2 arrives at R0+8680. tx_start for R1 at R0+wait+4340+434 = R0+wait+4774.
# Is R0+8680 > R0+wait+4774? 8680 > wait+4774? 8680 > 4774+433 = 5207? Yes!
# So R2 arrives AFTER tx_start for R1. Buffer is empty. R2 goes to buffer.
# 
# Hmm, so it works out. Let me trace more carefully.

print("\n--- Proper buffer simulation ---")
buffer_full = False
tx_done_at = float('inf')  # TX is idle initially
tx_start_at = None  # when TX will start next frame
max_buf = 0
drops = 0

# TX state: IDLE or BUSY
tx_idle = True
# When tx_start is asserted, TX starts at next baud_tick
# Frame takes 10*BAUD_DIV, then tx_done
# After tx_done, 1 baud IDLE, then if buffer full, tx_start

# Actually, the controller pops the buffer when TX is in IDLE.
# TX enters IDLE when tx_done fires. But in the controller FSM,
# TX_IDLE state: if buffer full, pop and tx_start.
# So the sequence is:
# 1. tx_done fires -> controller goes to TX_IDLE (next cycle)
# 2. In TX_IDLE, if buffer full: tx_start, clear buffer, go to TX_WAIT
# 3. TX_WAIT: wait for tx_done
# 4. TX latches tx_start, starts frame at next baud_tick
# 5. Frame: 10 baud. tx_done fires. Go to 1.

# So the cycle is: tx_done -> 1 cycle -> tx_start -> wait for baud_tick -> 10 baud -> tx_done
# Total: 1 + (0 to 433) + 4340 = 4341 to 4774 clocks

# But the controller checks buffer in TX_IDLE. If buffer is empty, it stays in TX_IDLE.
# When a result arrives, buffer is filled. But the controller is in TX_IDLE,
# so on the NEXT clock, it sees buffer full and starts TX.

# Let me model this precisely:
# State: TX_IDLE or TX_WAIT
# In TX_IDLE: if buffer_full, tx_start=1, buffer_full=0, state=TX_WAIT
# In TX_WAIT: if tx_done, state=TX_IDLE

# TX module: latches tx_start, starts at next baud_tick, frame=10 baud, tx_done at end

# So: result arrives at R -> buffer_full=1
# If controller in TX_IDLE: next clock, tx_start=1, buffer_full=0, state=TX_WAIT
# TX latches start_req, starts at next baud_tick (wait 0-434)
# Frame: 10*434 = 4340. tx_done at start + 4340.
# Controller: tx_done -> TX_IDLE (next clock)
# If buffer_full: tx_start, etc.

# The cycle from one tx_start to the next (when back-to-back):
# tx_start at T -> frame starts at T+wait -> tx_done at T+wait+4340
# -> controller TX_IDLE at T+wait+4341 -> tx_start at T+wait+4341
# -> frame starts at T+wait+4341+wait2 -> tx_done at T+wait+4341+wait2+4340
# 
# The wait2 depends on baud_tick alignment. After tx_done (which fires on baud_tick),
# the controller takes 1 clock to go to TX_IDLE and assert tx_start.
# TX latches start_req. On the NEXT baud_tick, frame starts.
# tx_done fires at baud_tick. Next baud_tick is 434 clocks later.
# But the controller takes 1 clock, so start_req is set 1 clock after baud_tick.
# The next baud_tick is 433 clocks later. So wait2 = 433.
# 
# Total cycle: wait + 4340 + 1 + 433 + 4340 = wait + 8714
# No wait, that's two frames. Let me think about one cycle:
# tx_start at T -> wait (0-433) -> frame (4340) -> tx_done -> 1 clock -> tx_start
# Cycle = wait + 4340 + 1
# But the next tx_start's wait depends on baud_tick alignment.
# tx_done fires at baud_tick. 1 clock later, tx_start is asserted.
# TX latches start_req. Next baud_tick is 433 clocks later.
# So the next frame starts 433 clocks after tx_done.
# Cycle = wait + 4340 + 1 + 433 = wait + 4774
# For the first frame, wait = 0-433. For subsequent, wait = 433.
# So cycle = 433 + 4340 + 1 + 433 = 5207? No...
#
# Let me just trace clock by clock for a few frames.

# Actually, let me just check: with the current 128-deep FIFO, the test passes.
# The question is whether a 1-deep buffer also works. My simulation says max backlog = 1.
# But I need to account for the 1-clock controller latency and the baud_tick wait.
#
# The worst case cycle is: 433 (wait) + 4340 (frame) + 1 (controller) + 433 (wait) = 5207
# No, that's wrong. Let me think step by step:
# 
# Frame N:
# - tx_start asserted at time T (1-cycle pulse from controller)
# - TX latches start_req at T+1 (next posedge)
# - TX is in IDLE. On next baud_tick (at T+1+wait, wait=0..433), frame starts.
# - Frame: START(434) + DATA(8*434) + STOP(434) = 4340 clocks
# - tx_done fires at T+1+wait+4340 (on baud_tick)
# - Controller sees tx_done at T+1+wait+4340+1 (next posedge)
# - Controller goes to TX_IDLE, checks buffer
# - If buffer full: tx_start at T+1+wait+4340+1
# 
# Frame N+1:
# - tx_start at T+1+wait+4340+1
# - TX latches at T+1+wait+4340+2
# - wait2 for baud_tick: tx_done was at baud_tick T+1+wait+4340.
#   Next baud_tick at T+1+wait+4340+434.
#   start_req set at T+1+wait+4340+2. 
#   If 2 < 434, next baud_tick is at T+1+wait+4340+434. wait2 = 434-2 = 432.
# - Frame starts at T+1+wait+4340+434
# - tx_done at T+1+wait+4340+434+4340 = T+1+wait+9114
#
# Cycle = (T+1+wait+9114) - (T+1+wait+4340) = 4774
# So cycle = 4774 consistently (after the first frame).
# First frame: wait + 4340 + 1 = wait + 4341 (from tx_start to tx_done seen by controller)
# 
# So the cycle is 4774 clocks, and results come every 4340 clocks.
# Backlog grows by (4774-4340)/4340 = 0.1 per result.
# But row boundary gives 13020 clocks = 2.7 frames of catch-up.
# Per row: 30 results, backlog grows by 30*0.1 = 3.
# Row boundary: catch up 2.7. Net: 0.3 per row.
# Over 30 rows: 9. So backlog should reach 9!
#
# But my simulation shows 1. There's a discrepancy. Let me find the bug.

# The bug is in my simulation model. When TX is busy and a result arrives,
# I do: buffer_count += 1, then tx_busy_until += 4774, then buffer_count -= 1.
# This means the result is immediately consumed (buffer goes back to 0).
# But in reality, the result stays in the buffer until tx_done fires.
# 
# The correct model: 
# - When result arrives, if buffer is empty, store it (buffer=1)
# - When tx_done fires, if buffer=1, start TX, buffer=0
# - When result arrives and buffer=1, it OVERFLOWS (or needs depth 2)
#
# So I need to check: between two tx_done events, do 2 results arrive?
# tx_done period = 4774. Result period = 4340.
# 4774 / 4340 = 1.1. So sometimes 2 results arrive between tx_done events!
# When that happens, buffer overflows with a 1-deep buffer.
#
# Let me simulate properly.

print("=== Proper simulation with 1-deep buffer ===")
buffer = 0  # 0 or 1
tx_busy = False
tx_done_at = float('inf')  # when tx_done will fire (if busy)
tx_start_pending = False  # start_req latched
max_buffer = 0
drops = 0
results_transmitted = 0

# TX state
tx_state = "IDLE"  # IDLE, START, DATA, STOP
tx_state_end = 0  # when current TX state ends (baud_tick)

# Controller state
ctrl_state = "TX_IDLE"  # TX_IDLE or TX_WAIT

# I need to track events properly. Let me use a different approach:
# track when each result arrives and when each tx_done fires.

# Generate tx_done events based on when TX starts.
# TX starts when: controller is in TX_IDLE and buffer is full.
# Controller goes to TX_IDLE 1 clock after tx_done.

# Let me track:
# next_tx_done: when the next tx_done will fire (inf if TX idle)
# buffer: 0 or 1
# ctrl_ready: when controller will be in TX_IDLE (ready to start TX)

next_tx_done = float('inf')
ctrl_ready_at = 0  # controller is in TX_IDLE and ready
buffer = 0
max_buffer = 0
drops = 0

for i, rt in enumerate(result_times):
    # Result arrives at rt
    # First, process any tx_done that fires before rt
    while next_tx_done <= rt:
        # tx_done fires at next_tx_done
        # Controller goes to TX_IDLE 1 clock later
        ctrl_ready_at = next_tx_done + 1
        # Check if buffer has data to transmit
        if buffer > 0:
            buffer -= 1
            # TX starts: tx_start at ctrl_ready_at
            # TX latches at ctrl_ready_at + 1
            # Wait for baud_tick: next baud_tick after ctrl_ready_at + 1
            bt = next_baud_tick(ctrl_ready_at + 1)
            # Frame: 10*BAUD_DIV
            next_tx_done = bt + 10 * BAUD_DIV
            ctrl_ready_at = float('inf')  # controller is now in TX_WAIT
        else:
            # No data to transmit, TX stays idle
            next_tx_done = float('inf')
            # ctrl_ready_at stays at ctrl_ready_at (TX_IDLE)
    
    # Now process the result arriving at rt
    if next_tx_done == float('inf'):
        # TX is idle
        if ctrl_ready_at <= rt:
            # Controller is ready, start TX immediately
            buffer = 0  # result goes directly to TX
            bt = next_baud_tick(rt + 1)  # tx_start at rt, latched at rt+1
            next_tx_done = bt + 10 * BAUD_DIV
            ctrl_ready_at = float('inf')
        else:
            # Controller not ready yet (still in TX_WAIT from previous)
            buffer += 1
            if buffer > max_buffer:
                max_buffer = buffer
            if buffer > 1:
                drops += 1
                buffer = 1  # drop the excess
    else:
        # TX is busy
        buffer += 1
        if buffer > max_buffer:
            max_buffer = buffer
        if buffer > 1:
            drops += 1
            buffer = 1  # drop excess

print(f"Max buffer: {max_buffer}")
print(f"Drops: {drops}")
print(f"Results: {len(result_times)}")

# Hmm, this is getting complicated. Let me try a simpler approach:
# just track the buffer level over time.
print("\n=== Simpler approach: track buffer level ===")
# At any time, buffer_level = results_arrived - results_transmitted_started
# A result is "transmitted started" when tx_start is asserted for it.
# tx_start can only be asserted when TX is idle (controller in TX_IDLE).
# 
# The controller in TX_IDLE checks buffer. If full, tx_start.
# So results_transmitted_started increases when controller is in TX_IDLE
# and buffer is full.
#
# The controller is in TX_IDLE when:
# - Initially (after reset)
# - 1 clock after tx_done fires
#
# tx_done fires 10*BAUD_DIV after frame start.
# Frame start is at next baud_tick after tx_start.
# tx_start is 1 cycle after controller enters TX_IDLE with buffer full.
#
# This is circular. Let me just simulate clock by clock for a small example.

# Actually, let me just run the actual Verilog simulation with a 1-deep buffer
# and see if it passes. That's the definitive test.
print("Will test with actual Verilog simulation.")