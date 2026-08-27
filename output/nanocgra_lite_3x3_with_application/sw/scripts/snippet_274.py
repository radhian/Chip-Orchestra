import sys
sys.path.insert(0, '.')
from golden.model.top import sobel_stream
import json

with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
pixels = [p for row in grid['pixels'] for p in row]
out = sobel_stream(pixels)

# Check how many results are produced per pixel
# The golden model produces a result when col>=2 and row>=2
# First result at pixel index = 2*32+2 = 66
# Last result at pixel index = 31*32+31 = 1023
# Total results = 30*30 = 900
# So results are produced at pixels 66..1023 (958 pixels), but only 900 produce results
# Actually results produced when col>=2 and row>=2: that's 30*30=900 results

# Let's trace which pixel indices produce results
results_indices = []
for idx in range(len(pixels)):
    row = idx // 32
    col = idx % 32
    if col >= 2 and row >= 2:
        results_indices.append(idx)
print("First result at pixel idx:", results_indices[0])
print("Last result at pixel idx:", results_indices[-1])
print("Total results:", len(results_indices))
print("Results per row: 30, rows with results: 30")

# Now let's think about the RTL timing
# BAUD_DIV = 434. Each byte takes 10 * 434 = 4340 cycles
# 1024 input bytes: 1024 * 4340 = 4,439,360 cycles to send all pixels
# 900 output bytes: 900 * 4340 = 3,906,000 cycles to send all results
# But TX and RX happen concurrently...
# The issue: the receiver in the TB blocks waiting for start bit.
# If the DUT produces results slower than the TB sends pixels, 
# the receiver might wait too long.

# Actually the problem is likely a deadlock or the DUT not producing all 900 results
# Let's check: the DUT has a result queue of depth 4.
# If the queue fills up (q_full), results are DROPPED (q_push = rx_valid && window_valid && !q_full)
# This means if TX is slower than pixel reception, the queue fills and results are lost!

# Let's calculate: 
# - Each pixel takes 10*434 = 4340 cycles to receive
# - Each result takes 10*434 = 4340 cycles to transmit  
# - Results start at pixel 66, so first result is produced while pixels are still coming
# - At steady state, 1 result per pixel, and TX takes same time as RX
# - But TX has overhead (FSM states TX_IDLE->TX_WAIT), and the queue is only depth 4

# The queue depth is 4. If 4 results accumulate before TX can drain them, 
# new results are dropped. Let's check if this happens.
# Actually, the first 66 pixels produce no results. Then results come 1 per pixel.
# TX starts draining when first result is in queue.
# TX takes 4340 cycles per result. RX takes 4340 cycles per pixel.
# So they should keep up with each other... unless there's a timing issue.

# Wait - the key issue: the TB sends pixels at 4340 cycles each.
# The DUT RX also takes 4340 cycles per byte (same baud).
# But the DUT TX also takes 4340 cycles per byte.
# So if results are produced at the same rate as pixels (1:1 at steady state),
# and TX and RX run at the same baud, they should keep up.

# BUT: the first result is produced at pixel 66. By then, 66*4340 = 286,440 cycles have passed.
# TX hasn't started yet. So there's a 66-pixel backlog.
# The queue depth is 4, so after 4 results, the queue is full and results are dropped!

# Actually wait - let me re-read the controller. The queue push happens on rx_valid.
# rx_valid pulses once per received byte. So results are pushed at the pixel rate.
# TX drains at the same rate. But there's a 66-pixel delay before the first result.
# During that delay, no results are produced, so queue stays empty.
# Once results start (pixel 66), they come 1 per pixel.
# TX starts draining. But TX takes 4340 cycles per result, same as pixel rate.
# So queue should stay at ~1-2 entries. Should be fine with depth 4.

# Hmm, but the simulation shows 800 captured then timeout.
# So it captures 800 of 900. Let me think about what could go wrong...

# Actually the issue might be simpler: the simulation takes too long due to real baud timing.
# 1024 pixels * 4340 cycles = 4.4M cycles for input
# 900 results * 4340 cycles = 3.9M cycles for output  
# Total ~8.3M cycles if sequential, but concurrent so ~4.4M + some overhead
# But the watchdog is 100M cycles! That should be enough.
# Unless there's a hang/deadlock.

# Let me check: 800 captured, then timeout at 100M cycles.
# 800 results * 4340 = 3.47M cycles for TX
# But the last 100 results might never come if the queue dropped them.

# Let me count: if queue fills up and drops results, we'd get fewer than 900.
# The TB receiver blocks forever waiting for the 801st byte that never comes.
# That's the timeout!

print("\n--- Queue overflow analysis ---")
print("Queue depth:", 4)
print("If queue overflows, results are dropped and TB hangs waiting for them")
print("Need to check if queue can overflow")

# Actually, let me reconsider. The first result is at pixel 66.
# Before pixel 66, no results, queue empty.
# At pixel 66, first result pushed. TX starts.
# TX takes 4340 cycles. Next pixel (67) arrives in 4340 cycles.
# So by the time pixel 67 arrives, TX might still be sending result 0.
# Result 1 is pushed. Queue = 1 (TX still busy).
# This continues... queue grows by 1 each pixel, drains by 1 each TX.
# Since TX and pixel rate are equal, queue stays bounded.
# But there's a phase offset: TX starts 1 pixel after first result.
# So queue oscillates between 0 and 1. Should be fine.

# Wait, but there's the TX FSM: TX_IDLE -> (pop, tx_start) -> TX_WAIT -> (tx_done) -> TX_IDLE
# The pop happens in TX_IDLE. Then TX_WAIT waits for tx_done.
# tx_done comes after 10 baud periods = 4340 cycles.
# But the next pop can only happen after tx_done.
# So TX throughput is 1 result per 4340 cycles, same as pixel rate.
# But there's a 1-cycle overhead between TX_WAIT and TX_IDLE.
# Actually no, it's combinational - TX_WAIT sees tx_done and goes to TX_IDLE same cycle.
# But tx_start is asserted in TX_IDLE, and the TX module latches it.
# The TX module then takes 10 baud periods.
# So effectively 1 result per 4340 cycles + a few cycles overhead.
# This means TX is SLIGHTLY slower than pixel rate!
# Over 900 results, the backlog grows by ~900 * few_cycles = ~thousands of cycles.
# But the queue is only depth 4. If backlog exceeds 4, results are dropped!

# Hmm, but the overhead is just a few cycles per 4340, so it takes ~4340/few = ~1000 results
# to accumulate 1 extra queue entry. Over 900 results, maybe 1 queue overflow.
# That could explain 800 captured (some dropped near the end).

# Actually, let me think more carefully. The TB sends pixels at exactly 4340 cycles each.
# The DUT RX receives them at 4340 cycles each (same baud).
# The DUT TX sends at 4340 cycles each (same baud).
# But the DUT TX has a 1-cycle gap between frames (TX_IDLE -> TX_WAIT -> TX_IDLE).
# Actually, tx_done pulses for 1 cycle, then TX_IDLE, then tx_start, then TX starts.
# The TX module latches tx_start on any clock, then waits for next baud tick.
# If baud_cnt is mid-count, there's up to 434 cycles of delay before the start bit.
# But the TX module RESETS baud_cnt when starting! So it's always 434 cycles per bit.
# Wait no - it resets baud_cnt to 0 when going IDLE->START. So the start bit is 434 cycles.
# Then 8 data bits * 434 = 3472. Then stop bit 434. Total = 434*10 = 4340.
# But between tx_done and the next tx_start, there's at least 1 cycle in TX_IDLE.
# And the TX module needs to latch tx_start, then wait for baud_tick.
# But baud_cnt was reset to 0 at the start of the previous frame.
# After the stop bit, baud_cnt continues from where it was.
# Actually, the TX resets baud_cnt only when going IDLE->START.
# After STOP, it goes to IDLE. baud_cnt continues counting.
# When tx_start is latched and next baud_tick comes, it goes to START and resets baud_cnt.
# So there's up to 434 cycles of delay waiting for the baud_tick after tx_start.

# This means TX throughput is 4340 + up_to_434 = up to 4774 cycles per result.
# vs pixel rate of 4340. So TX is up to 10% slower!
# Over 900 results, backlog grows by up to 900 * 434/4340 = 90 entries.
# Queue depth 4 is WAY too small. Results are dropped after the first ~4-40.

# But the sim shows 800 captured... so maybe the timing works out differently.
# Let me just check: the real issue is likely that the queue is too small
# OR the TB baud timing doesn't match the DUT baud timing exactly.

# Actually, re-reading the TB: the TB sends at BAUD_DIV=434 cycles per bit.
# The DUT RX uses baud_gen which also counts to 434. So they're synchronized.
# But the DUT RX detects start bit on falling edge at a baud_tick.
# The TB drives the start bit for 434 cycles. The DUT samples at baud_tick.
# There might be a phase offset, but it should work.

# The real issue: the DUT TX is slower than the pixel rate due to baud alignment.
# Let me just increase the queue depth to fix this.
# Or better: make the controller not drop results when queue is full.
# But we can't buffer infinitely... 

# Actually the cleanest fix: increase queue depth to something large like 64 or 128.
# Or even better: make the TX not reset baud_cnt, so it's always aligned.
# But the TB receiver needs to sync to the start bit anyway.

# Let me think about this differently. The TB receiver waits for start bit (falling edge).
# So the DUT TX can start at any time - the TB receiver will catch it.
# The issue is purely throughput: if TX is slower than RX, queue overflows.

# The simplest fix: increase queue depth. Let's calculate the max backlog.
# Worst case: TX takes 4340+434 = 4774 cycles per result (waiting for baud tick).
# RX produces 1 result per 4340 cycles.
# Backlog growth rate: (4774-4340)/4340 = 0.1 results per result.
# Over 900 results: 90 backlog. So queue depth needs to be ~90+.
# Let's use 128 to be safe.

# But wait - the queue is only 3-bit count (0..7) and 2-bit pointers (0..3).
# We need to widen these. Let's use depth 128, 7-bit pointers, 8-bit count.

# Actually, let me reconsider. Maybe the issue is simpler.
# Let me re-read the controller's TX FSM more carefully.

print("\n--- Controller TX FSM analysis ---")
print("TX_IDLE: if q_pop (queue not empty), pop result, assert tx_start, go to TX_WAIT")
print("TX_WAIT: wait for tx_done, increment out_cnt, go to TX_IDLE")
print("")
print("The issue: tx_start is asserted for only 1 cycle (it's a pulse).")
print("The TX module latches tx_start on any clock. Good.")
print("But between TX_WAIT->TX_IDLE and the next TX_IDLE->TX_WAIT,")
print("there's 1 cycle in TX_IDLE where q_pop is checked.")
print("If queue is empty, it stays in TX_IDLE. If not, it pops.")
print("")
print("The TX module takes 10 baud periods = 4340 cycles per byte.")
print("But the TX module's baud_cnt is free-running after reset.")
print("When tx_start is latched, it waits for the next baud_tick.")
print("This can take 0..433 cycles. So TX takes 4340..4773 cycles.")
print("")
print("The pixel rate is exactly 4340 cycles (TB sends at this rate).")
print("So TX is slower by 0..433 cycles per result.")
print("Over 900 results, backlog can grow by up to 900*433/4340 ≈ 90")
print("Queue depth 4 is insufficient. Need ~128.")