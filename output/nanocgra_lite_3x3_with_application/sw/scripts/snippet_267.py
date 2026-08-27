# 800 captured but then timeout. The issue is the last 100 results.
# The sender finishes sending all 1024 pixels, but the receiver is still
# waiting for the last results. The controller's TX queue might have
# results that haven't been sent yet.
# 
# After all pixels are sent, the fork/join waits for both processes.
# The sender finishes, but the receiver is still blocking on recv_byte_blocking.
# The controller should still be sending remaining results from the queue.
# 
# But the receiver's recv_byte_blocking waits forever for data_o to go low.
# If the controller has finished sending all 900 results, data_o stays high
# and the receiver blocks forever -> timeout.
# 
# The issue: the receiver loop is `while (n_captured < N_RESULTS)`.
# It captured 800, then waits for the 801st. But maybe the controller
# only produced 800 results? Or the last results are stuck in the queue?
# 
# Wait, 800 is a suspiciously round number. Let me check if the issue
# is that the receiver misses some results due to timing.
# 
# Actually, the problem might be that the sender finishes before the
# receiver captures all results. The fork/join waits for BOTH to finish.
# The sender finishes after sending 1024 pixels. The receiver is still
# capturing. But the controller might still be sending results from
# its queue.
# 
# The receiver should keep going until it captures 900. But if the
# controller has already sent all 900 and the receiver missed some,
# it will block forever.
# 
# Let me check: does the receiver miss any results? The recv_byte_blocking
# has no timeout, so it waits forever. If the controller sends a result
# while the receiver is still processing the previous one, the receiver
# might miss the start bit.
# 
# The recv_byte_blocking takes about 10 baud periods per byte. The
# controller sends results from the queue as fast as it can. If the
# queue has multiple results, they're sent back-to-back. The receiver
# should catch each one because after finishing one byte, it immediately
# waits for the next start bit.
# 
# But there's a gap between the stop bit of one frame and the start bit
# of the next. The UART TX goes STOP -> IDLE -> START on consecutive
# baud ticks. So there's 1 baud period of idle (high) between frames.
# The receiver should see this and wait for the next start bit.
# 
# Actually, the STOP state sets tx_out=1 and goes to IDLE. Then in IDLE,
# if start_req, it goes to START with tx_out=0. So the stop bit is 1
# baud period, then immediately the start bit of the next frame. There's
# no gap between frames.
# 
# The receiver finishes sampling the last data bit, waits 1 baud period
# for the stop bit, then returns. At this point, the next frame's start
# bit might have already begun! The receiver calls recv_byte_blocking
# again, which waits for data_o=0. But if the next start bit already
# happened, data_o might be in the middle of a data bit (could be 0 or 1).
# 
# If data_o is 1 at that moment, the receiver waits. But the next start
# bit won't come until the controller sends the next result. If the
# controller is still sending the current frame, the receiver misses it.
# 
# This is the same timing issue as before, but now with back-to-back frames.
# 
# The fix: add a small idle gap between TX frames. This gives the receiver
# time to finish and start waiting for the next start bit.
# 
# Let me add a 1-baud-period idle gap in the UART TX between frames.
# In the STOP state, instead of going directly to IDLE, go to an
// intermediate IDLE_GAP state that holds tx_out=1 for one baud period
# before going to IDLE.

# Actually, the STOP state already holds tx_out=1 for 1 baud period.
# Then IDLE also holds tx_out=1. So there IS a gap if the controller
# doesn't immediately start the next TX. But if the queue has results,
# the controller pops the next one immediately in TX_IDLE.
# 
# The issue is that the controller's TX_IDLE pops and starts TX on the
# same cycle as tx_done. So the UART TX sees tx_start=1 while it's
# transitioning from STOP to IDLE. The UART TX latches tx_start and
# starts the next frame on the next baud tick.
# 
# So the timeline is:
# - STOP baud tick: tx_out=1, tx_done=1, state=IDLE
# - Next cycle: controller sees tx_done, pops queue, sets tx_start=1
# - UART TX latches tx_start=1
# - Next baud tick: UART TX in IDLE sees start_req=1, starts new frame
# 
# So there's 1 baud period of IDLE (high) between the stop bit and the
# next start bit. The receiver should see this.
# 
# But the receiver's recv_byte_blocking returns after:
# - 8 data bits (8*434 = 3472 cycles)
# - 1 stop bit wait (434 cycles)
# Total from start bit detection: 651 + 3472 + 434 = 4557 cycles
# 
# The TX frame is 4340 cycles (10 baud periods).
# The receiver takes 4557 cycles, which is 217 cycles MORE than the frame.
# So the receiver finishes 217 cycles AFTER the stop bit ends.
# 
# But the next frame starts 1 baud period (434 cycles) after the stop bit.
# So the next start bit is at 4340 + 434 = 4774 cycles from the first start bit.
# The receiver finishes at 4557 cycles from the first start bit detection
# (which is ~2 cycles after the start bit began, so ~4559 from start bit).
# 4559 < 4774, so the receiver has 215 cycles to start waiting before the
# next start bit. This should be enough.
# 
# But wait, the receiver's stop bit wait is only 434 cycles. The stop bit
# lasts 434 cycles. So the receiver finishes right at the end of the stop
# bit. Then the next frame starts immediately (or after 1 IDLE baud period).
# 
# Hmm, let me recalculate more carefully.
# 
# Receiver timeline (from start bit detection at t=0):
# t=0: detect start bit (data_o=0)
# t=651: sample bit 0
# t=1085: sample bit 1
# ...
# t=3689: sample bit 7
# t=4123: stop bit wait done (3689+434=4123)
# recv_byte_blocking returns at t=4123
# 
# TX timeline (from start bit at t=-2, since detection is 2 cycles late):
# t=-2: start bit begins (tx_out=0)
# t=432: bit 0 begins
# t=866: bit 1 begins
# ...
# t=3468: bit 7 begins
# t=3902: stop bit begins (tx_out=1)
# t=4336: stop bit ends, IDLE begins
# t=4770: next start bit (if queue has next result)
# 
# Receiver returns at t=4123. Next start bit at t=4770.
# 4770 - 4123 = 647 cycles. The receiver has 647 cycles to start waiting.
# Since recv_byte_blocking immediately checks data_o, and data_o=1 (in
# stop bit or IDLE), it starts waiting. Good.
# 
# So the receiver should catch the next start bit at t=4770.
# 
# But what about the 800-result limit? Let me check if the controller
# actually produces 900 results. The issue might be that the queue
# overflows and some results are lost.
# 
# The queue depth is 4. If the controller produces results faster than
# the TX can send them, the queue fills up and results are dropped.
# 
# At steady state (row>=2, col>=2), every pixel produces a result.
# The pixels arrive at 1 per 10 baud periods (send_byte rate).
# The TX sends at 1 per ~10 baud periods. So the production and
# consumption rates are about the same. The queue shouldn't overflow.
# 
# But there might be a burst at the beginning. When row reaches 2,
# the first 30 results (cols 2-31) are produced in 30 consecutive
# pixels. The TX can only send 1 per 10 baud periods. So the queue
# fills up quickly.
# 
# Wait, the pixels arrive at 1 per 10 baud periods (send_byte rate).
# The TX sends at 1 per ~10 baud periods. So they're matched.
# The queue should stay at 0-1 entries.
# 
# But with the concurrent sender/receiver, the sender sends pixels
# as fast as it can. The receiver captures results as fast as it can.
# The sender and receiver run independently.
# 
# The sender takes 4340 cycles per pixel. The receiver takes ~4557
# cycles per result. The TX takes 4340 cycles per result.
# 
# So the production rate is 1 result per 4340 cycles (pixel rate).
# The consumption rate is 1 result per 4340 cycles (TX rate).
# They're matched. The queue should stay small.
# 
# But the receiver takes 4557 cycles, which is slower than the TX's
# 4340 cycles. So the receiver might miss some start bits if the TX
# sends faster than the receiver can process.
# 
# Wait, the receiver and TX are independent. The TX sends at its own
# pace (4340 cycles per frame). The receiver captures at its own pace
# (4557 cycles per frame). If the TX sends faster, the receiver falls
# behind and misses frames.
# 
# TX frame interval: 4340 + 434 (IDLE gap) = 4774 cycles
# Receiver frame interval: 4557 cycles
# 
# 4557 < 4774, so the receiver is FASTER than the TX. Good, the
# receiver should catch every frame.
# 
# Hmm, but 800 out of 900 were captured. Let me check if the issue
# is at the end of the simulation. After all 1024 pixels are sent,
# the sender finishes. The receiver is still waiting for the last
# 100 results. The controller should still be sending from its queue.
# 
# But maybe the queue is empty and the controller has already sent
# all results? Let me check: 1024 pixels, 900 results. The last result
# is at pixel 1023 (row=31, col=31). After that, the controller has
# no more results to send. If the receiver captured 800, it missed 100.
# 
# The issue might be that the receiver misses the last few results
# because of a race condition at the end.
# 
# Actually, let me just increase the timeout and add some debug.
# Or better, let me check if the queue overflows during the burst
# at the start of each row.
# 
# When a new row starts (col=0,1), no results are produced (col<2).
# This gives the TX time to drain the queue. Then at col=2..31,
# 30 results are produced in 30 consecutive pixels. The TX sends
# them at the same rate. So the queue should stay at 0-1.
# 
# Wait, but the sender and receiver are now concurrent. The sender
# sends pixels as fast as it can. The receiver captures results.
# But the sender doesn't wait for the receiver. So the sender might
# send all 1024 pixels before the receiver captures all 900 results.
# 
# After the sender finishes, the fork/join waits for the receiver.
# The receiver is still blocking on recv_byte_blocking. The controller
# should still be sending results from its queue.
# 
# But if the queue was drained during the sending phase, and the
# controller has already sent all 900 results, the receiver might
# have missed some.
# 
# The key question: does the receiver miss any frames?
# 
# The receiver takes 4557 cycles per frame. The TX takes 4774 cycles
# per frame (including IDLE gap). So the receiver is ready before the
# next frame starts. It should catch every frame.
# 
# But what if the TX sends frames back-to-back without an IDLE gap?
# Let me check the UART TX: after STOP, it goes to IDLE. In IDLE,
# if start_req, it goes to START on the next baud tick. So there's
# at least 1 baud period of IDLE. But the controller might set
# tx_start during this IDLE period, and the UART TX latches it.
# Then on the next baud tick, it starts the new frame. So the gap
# is exactly 1 baud period (the IDLE state).
# 
# Actually, the STOP state lasts 1 baud period (tx_out=1). Then IDLE
# starts. If start_req is already latched, IDLE lasts 1 baud period
# (until the next baud tick). Then START begins. So the total gap
# between the stop bit and the next start bit is 1 baud period (the
# IDLE state).
# 
# Wait, no. The STOP state sets tx_out=1 for 1 baud period. Then
# the state goes to IDLE. In IDLE, tx_out=1. On the next baud tick,
# if start_req, it goes to START with tx_out=0. So the gap is:
# STOP (1 baud) + IDLE (1 baud) = 2 baud periods of high.
# 
# No, the STOP state transitions to IDLE on the baud tick. So:
# - STOP baud tick: tx_out=1, tx_done=1, state=IDLE
# - IDLE: on next baud tick, if start_req, tx_out=0, state=START
# 
# So the stop bit is 1 baud period, then IDLE is 1 baud period,
# then the next start bit. Total gap = 2 baud periods of high.
# 
# The receiver finishes at 4557 cycles from start bit detection.
# The TX frame is 10 baud periods = 4340 cycles. The gap is 2 baud
# periods = 868 cycles. So the next start bit is at 4340+868 = 5208
# cycles from the first start bit.
# 
# The receiver finishes at 4557 cycles from start bit detection
# (which is ~2 cycles after start bit). So receiver finishes at
# ~4559 from start bit. Next start bit at 5208. 
# 5208 - 4559 = 649 cycles. The receiver has 649 cycles to start
# waiting. Plenty of time.
# 
# So the receiver should catch every frame. Why only 800?
# 
# Let me check if the issue is the queue overflow. With QDEPTH=4,
# if the controller produces 4 results before the TX can send any,
# the queue fills up and subsequent results are dropped.
# 
# At the start of row 2, the first result is at pixel 66 (col=2).
# The next 29 results are at pixels 67-95 (cols 3-31). These arrive
# at 1 per 4340 cycles (send_byte rate). The TX sends at 1 per ~4774
# cycles. So the queue grows by 1 every 4340 cycles and shrinks by 1
# every 4774 cycles. The net growth is 1 - 4340/4774 = 0.091 per
# result. Over 30 results, the queue grows by 30*0.091 = 2.7.
# So the queue reaches about 3. With QDEPTH=4, it barely fits.
# 
# But over 30 rows, the queue accumulates: 30*30*0.091 = 82.
# That's way more than 4! The queue overflows and results are dropped!
# 
# Wait, that can't be right. The production rate is 30 results per
# 30*4340 = 130200 cycles (one row of pixels). The consumption rate
# is 30 results per 30*4774 = 143220 cycles. So the queue grows by
# 30 per 130200 cycles and shrinks by 30 per 143220 cycles. The net
# growth per row is 30 * (1 - 130200/143220) = 30 * 0.091 = 2.7.
# 
# Over 30 rows, the queue grows by 30*2.7 = 81. With QDEPTH=4, the
# queue overflows after about 4/2.7 = 1.5 rows. So about 45 results
# are produced before the queue overflows. After that, results are
# dropped.
# 
# But the simulation shows 800 captured, not 45. So the queue isn't
# overflowing that badly. Let me reconsider.
# 
# Actually, the production rate is NOT 1 per 4340 cycles. The sender
# sends pixels at 4340 cycles each, but the receiver is also running.
# The sender and receiver are independent. The sender sends all 1024
# pixels as fast as it can. The receiver captures results.
# 
# The sender takes 1024 * 4340 = 4,444,160 cycles to send all pixels.
# The TX sends 900 results at 4774 cycles each = 4,296,600 cycles.
# So the TX is slightly faster than the sender. The queue should
# stay near 0.
# 
# Wait, 4,296,600 < 4,444,160. So the TX finishes before the sender.
# The queue should stay at 0-1 throughout. No overflow.
# 
# So why only 800 captured? Let me check if the receiver misses some
# frames due to timing.
# 
# The receiver takes 4557 cycles per frame. The TX sends at 4774 cycles
# per frame. So the receiver is faster. But what if the receiver
# occasionally takes longer? For example, if the start bit detection
# is delayed.
# 
# Actually, let me just check: is 800 a hard limit or does it vary?
# Let me look at the exact output more carefully.

print("Need to investigate why only 800 results are captured")
print("The issue might be at the end - after sender finishes, receiver")
print("can't catch the last results because of timing")