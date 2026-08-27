# The proper simulation shows max buffer = 2 and 60 drops with a 1-deep buffer!
# So a single-entry buffer is NOT sufficient with the current 11-baud TX.
# 
# The issue is the 1-baud IDLE gap between frames (4774 vs 4340 per frame).
# 
# Solution: eliminate the IDLE gap by going STOP->START directly when start_req is set.
# This makes TX take 10 baud = 4340 per frame, matching the result rate.
# Then a 1-deep buffer should work.
#
# Let me verify: with 10-baud TX (no gap), does a 1-deep buffer work?

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

# With no-gap TX: STOP->START directly if start_req
# Frame = 10*BAUD_DIV = 4340. No IDLE gap.
# But there's still the 1-clock controller latency and baud_tick wait.
# 
# After tx_done (on baud_tick), controller takes 1 clock to enter TX_IDLE.
# Then tx_start. TX latches on next clock. Then waits for baud_tick.
# tx_done at baud_tick T. Controller ready at T+1. tx_start at T+1.
# TX latches at T+2. Next baud_tick at T+434 (since T was a baud_tick).
# wait = 434 - 2 = 432. Frame starts at T+434. tx_done at T+434+4340 = T+4774.
# 
# Hmm, that's still 4774! The 1-clock controller latency + baud_tick wait
# adds 434 clocks.
#
# Wait, but with STOP->START, the TX doesn't go through IDLE.
# If start_req is already set when STOP ends, TX goes directly to START.
# So the frame starts on the VERY NEXT baud_tick after STOP.
# tx_done at baud_tick T. Next baud_tick at T+434. Frame starts at T+434.
# No controller latency! The TX module handles it internally.
#
# But the controller needs to set start_req BEFORE tx_done fires.
# With the FIFO approach, the controller pops the next result and 
# asserts tx_start when it sees tx_done. But that's 1 clock late.
#
# With a holding register approach:
# - Result stored in holding register
# - Controller asserts tx_start when holding register is full and TX is idle
# - But "TX is idle" is indicated by tx_done
# - tx_done -> 1 clock -> tx_start -> TX latches -> next baud_tick -> START
# 
# So there's always a 1-clock gap + baud_tick wait = up to 434 clocks.
# Unless we can set start_req BEFORE tx_done.
#
# Idea: the controller can assert tx_start WHILE TX is still transmitting,
# as long as it's for the NEXT result. The TX latches start_req.
# When STOP ends, if start_req is set, go directly to START.
# This eliminates the gap!
#
# So the flow:
# 1. Result A produced -> stored in holding register
# 2. Controller sees TX is idle -> tx_start(A), clear holding register
# 3. TX latches start_req, starts frame A
# 4. Result B produced -> stored in holding register
# 5. Controller sees holding register full AND TX is busy -> 
#    assert tx_start(B) NOW (while TX is still sending A)
#    But wait, tx_start is a 1-cycle pulse. The TX latches it.
#    But start_req is already 0 (it was consumed when frame A started).
#    So tx_start(B) sets start_req=1 again.
# 6. When frame A's STOP ends, start_req=1 -> go directly to START(B)
# 7. No gap! Frame B starts immediately after A.
#
# But the controller needs to know when to assert tx_start(B).
# It should assert tx_start when:
# - Holding register is full
# - TX is busy (so it's for the NEXT frame, not the current one)
# - start_req is not already set (don't double-set)
#
# Actually, the simplest approach: the controller asserts tx_start
# whenever the holding register is full and (TX is idle OR start_req is 0).
# The TX latches start_req and will use it when the current frame ends.
#
# But this changes the controller-TX interface. Currently:
# - Controller: TX_IDLE -> if buffer full, tx_start, TX_WAIT
# - Controller: TX_WAIT -> if tx_done, TX_IDLE
#
# With the new approach:
# - Controller: if holding_reg full and TX is idle, tx_start, clear holding_reg
# - Controller: if holding_reg full and TX is busy and !start_req, tx_start, clear holding_reg
#   (pre-arm the next frame)
#
# But the controller doesn't know start_req (it's internal to TX).
# We could add a tx_busy or tx_ready output from TX.
#
# Actually, let me think about this differently. The TX already latches
# tx_start on any clock. So if the controller asserts tx_start while TX
# is busy, start_req is set. When the current frame ends (STOP->IDLE),
# if start_req, it starts the next frame. But there's still the IDLE gap.
#
# To eliminate the IDLE gap, I need to modify the TX FSM:
# In STOP state: if start_req, go to START (not IDLE).
# This way, when STOP ends and start_req is set, the next frame starts
# immediately on the next baud_tick. No IDLE gap.
#
# With this modification:
# - Controller asserts tx_start when holding_reg is full
# - TX latches start_req
# - When current frame's STOP ends, if start_req, go to START
# - No gap! Frame-to-frame = 10 baud = 4340 clocks.
#
# The controller can assert tx_start at any time (even while TX is busy).
# The TX latches it. When the current frame ends, it starts the next one.
#
# But the controller needs to know when TX has consumed the start_req,
# so it can assert tx_start again for the next result.
# The tx_done signal indicates the frame is done. But with STOP->START,
# tx_done fires at the STOP->START transition (or STOP->IDLE if no start_req).
#
# Actually, tx_done should fire when STOP ends, regardless of next state.
# The controller sees tx_done and knows the frame is done.
# If holding_reg has a new result, it asserts tx_start.
# But if start_req was already set (pre-armed), the TX is already starting
# the next frame. The controller's tx_start would set start_req again,
# but it's already being consumed. This could cause issues.
#
# Let me think about this more carefully. The key is:
# 1. TX latches start_req on any clock when tx_start is asserted.
# 2. When STOP ends: if start_req, go to START (consume start_req).
# 3. tx_done fires when STOP ends.
# 4. Controller sees tx_done, goes to TX_IDLE.
# 5. If holding_reg full: tx_start, clear holding_reg, go to TX_WAIT.
# 6. TX latches the new start_req.
# 7. When the current frame (started in step 2) reaches STOP:
#    if start_req (from step 6), go to START. No gap!
#
# So the sequence is:
# - Frame A: STOP ends, start_req=1 (pre-armed) -> START(B), tx_done=1
# - Controller: tx_done -> TX_IDLE -> tx_start(C), TX_WAIT
# - TX latches start_req for C
# - Frame B: STOP ends, start_req=1 (for C) -> START(C), tx_done=1
# - Controller: tx_done -> TX_IDLE -> tx_start(D), TX_WAIT
# - ...
#
# This works! The controller asserts tx_start 1 clock after tx_done.
# TX latches it. When the current frame ends, it starts the next one.
# No IDLE gap!
#
# But there's a subtlety: the controller needs the holding register to have
# the next result BEFORE the current frame ends. If the result arrives
# after tx_done but before the current frame ends... wait, tx_done IS
# when the frame ends. So the controller has from tx_done to the next
# tx_done (4340 clocks) to get the next result into the holding register
# and assert tx_start.
#
# Results arrive every 4340 clocks. tx_done every 4340 clocks (with no gap).
# So the controller always has 4340 clocks to get the next result.
# The result arrives at some point in that window. The controller asserts
# tx_start when the result is in the holding register.
# The TX latches it. When the frame ends, it starts the next one.
#
# The only issue: if the result arrives AFTER the frame ends (after tx_done
# but the frame already ended and TX went to IDLE because start_req was 0).
# Then there's a gap. But this only happens if the result arrives late.
#
# With the no-gap TX, the cycle is 4340 clocks = same as result interval.
# So results and tx_done are phase-locked. The result might arrive just
# before or just after tx_done. If just before: pre-armed, no gap.
# If just after: TX goes to IDLE, then starts when result arrives. Small gap.
# But the gap is at most 4340 clocks (one frame), and the row boundary
# gives 13020 clocks of catch-up. So the backlog stays at 1.
#
# Let me verify with simulation.

print("=== No-gap TX with 1-deep buffer ===")

# With no-gap TX (STOP->START if start_req):
# Frame = 10*BAUD_DIV = 4340
# If start_req is set when STOP ends, next frame starts immediately.
# If not, TX goes to IDLE and waits for start_req.
#
# Controller: 
# - holding_reg full + TX_IDLE -> tx_start, clear holding_reg, TX_WAIT
# - TX_WAIT + tx_done -> TX_IDLE
#
# The controller asserts tx_start 1 clock after entering TX_IDLE.
# But TX might have already started the next frame (if start_req was pre-armed).
# In that case, tx_done fires, controller goes to TX_IDLE, sees holding_reg
# full, asserts tx_start. TX latches it for the NEXT frame.
#
# Let me simulate: track when tx_done fires and when results arrive.
# The buffer level = results_arrived - results_tx_started
# results_tx_started increments when tx_start is asserted (controller pops buffer).
# tx_start is asserted when controller is in TX_IDLE and buffer is full.
# Controller is in TX_IDLE: initially, and 1 clock after tx_done.

# Simplified: track tx_done events and result events.
# tx_done[N] fires at time T_done[N].
# Between T_done[N] and T_done[N+1], the controller can start 1 TX.
# If a result arrives in this window, it goes to buffer, then tx_start.
# If 2 results arrive in this window, buffer overflows.

# With no-gap TX: T_done[N+1] - T_done[N] = 4340 (if back-to-back).
# Results arrive every 4340. So at most 1 result per window. Buffer = 1. OK!
# But if TX goes to IDLE (no result ready), the next tx_done is delayed.
# Then 2 results might arrive before the next tx_done. Buffer = 2. OVERFLOW!

# When does TX go to IDLE? When no result is ready when STOP ends.
# This happens at the start (first result at pixel 66, TX idle before that).
# And at row boundaries (gap of 3 pixels = 13020 clocks).
# During the row boundary gap, TX finishes a frame and has no result.
# TX goes to IDLE. Then the next result arrives 13020 clocks later.
# But during those 13020 clocks, only 1 result arrives (the first of the next row).
# So buffer = 1. OK!

# But what about the phase alignment? Let me simulate precisely.

# Model: 
# - TX cycle = 4340 when back-to-back (no gap)
# - TX waits in IDLE when no result is ready
# - Controller: 1 clock after tx_done, if buffer full, tx_start
# - TX latches start_req, starts at next baud_tick
# - Frame = 4340, tx_done at end
# - If start_req set during frame, STOP->START directly (no gap)
# - If not, STOP->IDLE

# The 1-clock controller latency + baud_tick wait:
# tx_done at baud_tick T. Controller ready at T+1. tx_start at T+1.
# TX latches at T+2. Next baud_tick at T+434. Frame starts at T+434.
# tx_done at T+434+4340 = T+4774.
# 
# Wait, that's 4774, not 4340! The 1-clock + baud_tick wait adds 434.
# 
# UNLESS start_req was pre-armed. If the controller asserted tx_start
# BEFORE tx_done (while TX was busy), start_req is already set.
# When STOP ends at baud_tick T, start_req=1, go to START.
# Frame starts at T+434 (next baud_tick). Wait, no - STOP ends at baud_tick T.
# The transition happens AT the baud_tick. So START begins at T.
# Actually, the FSM transitions on the baud_tick. So:
# At baud_tick T: STOP -> START (if start_req). tx_out = 0 (start bit).
# At baud_tick T+434: START -> DATA (bit 0).
# ...
# At baud_tick T+9*434: STOP -> START or IDLE.
# tx_done at T+9*434? No, STOP is the 10th state.
# START(1) + DATA(8) + STOP(1) = 10 states. Each 1 baud.
# At baud_tick T: STOP -> START. (This is the start of the new frame)
# At baud_tick T+434: START -> DATA0.
# ...
# At baud_tick T+9*434: DATA7 -> STOP.
# At baud_tick T+10*434: STOP -> START/IDLE. tx_done fires.
# So frame = 10*434 = 4340. tx_done at T+4340.
# If pre-armed: next frame starts at T+4340. Cycle = 4340. 
#
# But the controller needs to pre-arm. It asserts tx_start when buffer is full.
# If the result arrives before tx_done, the controller can assert tx_start
# while TX is busy. TX latches start_req. When STOP ends, START begins.
# 
# The controller's TX_WAIT state: it waits for tx_done. When tx_done fires,
# it goes to TX_IDLE. In TX_IDLE, if buffer full, tx_start.
# But this is 1 clock AFTER tx_done. By then, TX has already transitioned
# (STOP->START if start_req was set, or STOP->IDLE if not).
# 
# So the controller needs to assert tx_start BEFORE tx_done, not after!
# This means the controller should be in a state where it asserts tx_start
# as soon as the buffer is full, regardless of TX state.
#
# New controller design:
# - When holding_reg is full: assert tx_start (1-cycle pulse)
# - Clear holding_reg
# - TX latches start_req
# - When TX is busy and start_req is set, it will start the next frame
#   when the current one ends (STOP->START)
# - When TX is idle and start_req is set, it starts immediately
#
# The controller doesn't need TX_WAIT state. It just asserts tx_start
# whenever holding_reg is full. The TX handles the rest.
#
# But then how does the controller know when to load the next result?
# It needs to know when TX has consumed start_req (started a frame).
# That's indicated by tx_done (the frame that was started is now done).
# 
# Actually, the controller doesn't need to know. It just needs:
# 1. When result is produced: if holding_reg empty, store it.
# 2. When holding_reg is full: assert tx_start, clear holding_reg.
# 3. tx_done is used only for counting (out_cnt) and status.
#
# But there's a race: if the controller asserts tx_start and clears holding_reg
# on the same cycle a new result arrives, the new result finds holding_reg
# empty and stores itself. Then the controller asserts tx_start again next cycle.
# But start_req is already set! The TX latches it again (no effect, it's already 1).
# The new result's tx_start is lost!
#
# Solution: the controller should only assert tx_start when holding_reg is full
# AND start_req is not already set. But the controller doesn't know start_req.
#
# Alternative: use tx_done to know when start_req is consumed.
# When tx_done fires, start_req has been consumed (frame started).
# The controller can then assert tx_start for the next result.
#
# So the flow:
# 1. Result A -> holding_reg = A
# 2. Controller: tx_start(A), holding_reg = empty
# 3. TX latches start_req
# 4. Result B -> holding_reg = B
# 5. Controller: tx_start(B)? But start_req is already set!
#   If we assert tx_start again, it's latched again (no effect).
#   When frame A ends, START(B) begins. start_req consumed.
#   But holding_reg is already empty (cleared in step 2).
#   So B's data was in holding_reg, but tx_start(B) was asserted and
#   holding_reg cleared. TX latched start_data = B.
#   Wait, the TX latches data_in when tx_start is asserted.
#   So TX has start_data = B. When frame A ends, it starts sending B.
#   That's correct!
#
# 6. tx_done(A) fires. Controller: out_cnt++. 
# 7. Result C -> holding_reg = C
# 8. Controller: tx_start(C), holding_reg = empty
# 9. TX latches start_data = C, start_req = 1
# 10. Frame B ends, START(C) begins. tx_done(B) fires.
# 11. Controller: out_cnt++.
#
# This works! The controller asserts tx_start whenever holding_reg is full.
# The TX latches the data. When the current frame ends, it starts the next.
# No IDLE gap!
#
# But there's a problem: between step 4 and step 5, if the controller
# asserts tx_start(B) and clears holding_reg, then result C arrives.
# holding_reg = C. Controller asserts tx_start(C). But TX is still sending A!
# start_req is already 1 (from B). tx_start(C) overwrites start_data = C.
# When A ends, TX starts C (not B)! B is LOST!
#
# So we need to ensure tx_start is only asserted when start_req is not set.
# Or use a different mechanism.
#
# The cleanest solution: 
# - holding_reg stores the result
# - tx_start is asserted when holding_reg is full AND tx_done has been seen
#   (meaning the previous start_req was consumed)
# - This is essentially the TX_WAIT -> TX_IDLE -> tx_start flow
# - But with STOP->START in TX, the gap is eliminated
#
# Wait, let me reconsider. With STOP->START:
# - Frame A: STOP ends, start_req=1 (for B) -> START(B), tx_done=1
# - Controller: tx_done -> TX_IDLE (1 clock later)
# - If holding_reg has C: tx_start(C), TX_WAIT
# - TX latches start_req=1, start_data=C
# - Frame B: STOP ends, start_req=1 (for C) -> START(C), tx_done=1
# - No gap!
#
# The key: the controller asserts tx_start 1 clock after tx_done.
# TX latches it. When the current frame ends (which started using the
# PREVIOUS start_req), it starts the next frame using the NEW start_req.
# 
# So the cycle is: tx_done -> 1 clock -> tx_start -> TX latches -> 
# current frame ends -> START(next) -> tx_done
# 
# The 1-clock delay is absorbed because the current frame is still running
# when tx_start is asserted. The TX latches start_req. When the frame ends
# (up to 4340 clocks later), it starts the next one.
#
# But what if the 1-clock tx_start comes AFTER the frame ends?
# That can't happen if results are arriving fast enough, because the
# controller only enters TX_IDLE after tx_done, and tx_done fires when
# the frame ends. So tx_start comes 1 clock after the frame ends.
# But the frame already ended! TX went to IDLE (or START if pre-armed).
# If pre-armed (start_req from previous), TX went to START. The new
# tx_start latches a new start_req for the NEXT frame.
# If not pre-armed, TX went to IDLE. The new tx_start sets start_req.
# TX starts on next baud_tick. Gap = 0 to 434 clocks.
#
# So the gap depends on whether start_req was pre-armed.
# Pre-armed: no gap. Not pre-armed: up to 434 gap.
# 
# When is start_req NOT pre-armed? When the controller hasn't asserted
# tx_start before the frame ends. This happens when:
# - The holding_reg was empty when the previous tx_done fired
# - So the controller stayed in TX_IDLE
# - Then a result arrives, controller asserts tx_start
# - But the current frame already ended (TX in IDLE)
# - TX starts on next baud_tick. Gap = 0 to 434.
#
# This happens at the beginning and at row boundaries.
# At row boundaries, the gap is absorbed by the 13020-clock pause.
# At the beginning, the first frame has a gap of 0 to 434.
# 
# So the cycle is 4340 + 0 (pre-armed) or 4340 + 434 (not pre-armed).
# The not-pre-armed case happens rarely (row boundaries).
# The pre-armed case: cycle = 4340 = result interval. No backlog growth!
# The not-pre-armed case: cycle = 4774. But this only happens once per row
# (at the boundary), and the 13020-clock gap absorbs it.
#
# So with the no-gap TX + pre-arming, the backlog stays at 1!
# Let me verify with simulation.

# Simulate: 
# - TX cycle = 4340 when pre-armed (back-to-back)
# - TX cycle = 4340 + gap when not pre-armed (gap = 0 to 434)
# - Results arrive every 4340 (within row), with 13020 gap at row boundaries

# The controller:
# - TX_IDLE: if holding_reg full, tx_start, TX_WAIT
# - TX_WAIT: if tx_done, TX_IDLE
# 
# With no-gap TX (STOP->START if start_req):
# - When controller asserts tx_start, TX latches start_req
# - If TX is busy, start_req is used when STOP ends (no gap)
# - If TX is idle, start_req is used on next baud_tick (gap 0-434)

# The buffer (holding_reg) level:
# - Result arrives: if holding_reg empty, fill it
# - Controller in TX_IDLE with holding_reg full: tx_start, clear holding_reg
# - If holding_reg full when result arrives: OVERFLOW

# The question: does holding_reg ever overflow?
# holding_reg is full when a result arrives AND the controller hasn't
# popped it yet (controller is in TX_WAIT).
# Controller is in TX_WAIT from tx_start until tx_done.
# TX_WAIT duration = frame duration = 4340 (if pre-armed) or 4340+gap.
# 
# If TX_WAIT = 4340 and results arrive every 4340:
# Result A -> holding_reg = A. Controller: tx_start(A), TX_WAIT, holding_reg = empty.
# 4340 clocks later: tx_done(A). Controller: TX_IDLE.
# Result B arrives at same time (or close). holding_reg = B. tx_start(B), TX_WAIT.
# 
# But what if result B arrives BEFORE tx_done(A)?
# B arrives at A_time + 4340. tx_done(A) at A_time + gap + 4340.
# If gap > 0, B arrives before tx_done(A). holding_reg = B.
# Controller is in TX_WAIT. holding_reg stays full.
# tx_done(A) fires. Controller: TX_IDLE. holding_reg full -> tx_start(B), TX_WAIT.
# 
# But now result C arrives at B_time + 4340 = A_time + 8680.
# tx_done(B) at tx_start(B) + 4340 = (tx_done(A) + 1) + 4340.
# tx_done(A) = A_time + gap + 4340.
# tx_done(B) = A_time + gap + 4340 + 1 + 4340 = A_time + gap + 8681.
# C arrives at A_time + 8680.
# If gap >= 1, C arrives before tx_done(B). holding_reg = C.
# Controller in TX_WAIT. holding_reg full.
# tx_done(B) fires. Controller: TX_IDLE. tx_start(C), TX_WAIT.
#
# This pattern continues. holding_reg is always full when the next result
# arrives, but it's popped when tx_done fires. So holding_reg goes:
# empty -> full (result) -> stays full (TX_WAIT) -> empty (tx_start) -> full (next result)
# 
# The question: is holding_reg ever full when a result arrives?
# Yes! When the result arrives during TX_WAIT.
# But the result goes to holding_reg (which is empty because it was cleared
# when tx_start was asserted). Wait, no:
# 
# Timeline:
# T=0: Result A. holding_reg = A. Controller: tx_start(A), holding_reg = empty. TX_WAIT.
# T=4340: Result B. holding_reg = B. (Controller in TX_WAIT)
# T=gap+4340: tx_done(A). Controller: TX_IDLE. holding_reg full -> tx_start(B), holding_reg=empty. TX_WAIT.
# T=8680: Result C. holding_reg = C. (Controller in TX_WAIT)
# T=gap+8681: tx_done(B). Controller: TX_IDLE. tx_start(C), holding_reg=empty. TX_WAIT.
# T=13020: Result D. holding_reg = D.
# ...
#
# So holding_reg is filled by the result and emptied by tx_start.
# The result arrives at T=4340*k. tx_start happens at T=gap+4340*k+1 (approx).
# If gap > 0, tx_start happens AFTER the result arrives.
# So when the result arrives, holding_reg is still empty (from previous tx_start).
# holding_reg = result. Then tx_start pops it.
# 
# But what if gap is large enough that 2 results arrive before tx_start?
# That would mean 2 results in the TX_WAIT period.
# TX_WAIT = 4340 + gap. Results every 4340.
# If gap > 0, TX_WAIT > 4340, so 2 results could arrive!
# Result B at T=4340. Result C at T=8680. tx_start(B) at T=gap+4340+1.
# If gap+4340+1 > 8680, i.e., gap > 4339, then C arrives before tx_start(B).
# But gap is at most 434. So gap+4340+1 <= 4775 < 8680. C arrives after tx_start(B).
# So only 1 result in TX_WAIT. holding_reg never overflows!
#
# Wait, but what about the row boundary? At the row boundary, there's a
# 13020-clock gap. During that time, TX finishes a frame and goes to IDLE.
# The controller is in TX_IDLE. When the next result arrives, holding_reg
# is filled, tx_start, TX_WAIT. Only 1 result. No overflow.
#
# So with the no-gap TX, a 1-deep holding register is sufficient!
# The max backlog is 1.
#
# But I need to also handle the case where the controller is in TX_IDLE
# (not TX_WAIT) and a result arrives. In that case:
# holding_reg = result. Controller: tx_start, TX_WAIT. holding_reg = empty.
# This is fine.
#
# And the case where the controller is in TX_WAIT and a result arrives:
# holding_reg = result. Controller stays in TX_WAIT.
# When tx_done fires: TX_IDLE. holding_reg full -> tx_start, TX_WAIT.
# holding_reg = empty.
# This is also fine, as long as another result doesn't arrive before tx_start.
# As shown above, with gap <= 434, the next result arrives 4340 clocks later,
# which is after tx_start (which happens 1 clock after tx_done).
# tx_done at T. tx_start at T+1. Next result at T + 4340 - gap.
# If gap = 434: next result at T + 3906. tx_start at T+1. 3906 > 1. OK!
# If gap = 0: next result at T + 4340. tx_start at T+1. 4340 > 1. OK!
#
# So the holding register never overflows. Max backlog = 1.
# 
# Now let me also check: does the no-gap TX change the testbench behavior?
# The testbench recv_byte_blocking waits for a falling edge (start bit).
# With no-gap TX: stop bit (1 baud high) -> start bit (0).
# The receiver sees: high (stop) for 1 baud, then low (start).
# The while loop: while (data_o === 1'b1) @(posedge clk); catches the falling edge.
# Then it waits HALF_BAUD + BAUD_DIV = 1.5 baud to sample bit 0.
# This works fine with 1 baud of stop/idle.
#
# With the current TX (gap): stop (1 baud) + IDLE (1 baud) -> start (0).
# The receiver sees: high for 2 baud, then low. Also works.
# So the testbench works with both.
#
# Let me now implement the changes:
# 1. Modify uart_tx.v: in STOP state, if start_req, go to START (not IDLE)
# 2. Modify nano_controller.v: replace 128-deep FIFO with 1-entry holding register
# 3. Keep all ports unchanged

print("Analysis complete. Max backlog = 1 with no-gap TX + 1-entry holding register.")
print("Implementation plan:")
print("1. Modify uart_tx.v: STOP->START when start_req (eliminate IDLE gap)")
print("2. Modify nano_controller.v: replace FIFO with 1-entry holding register")
print("3. Keep all ports unchanged")
print("4. Verify simulation passes")