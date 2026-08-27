import json
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# warmup=3 gives first tx_out=0 at vec 430. Perfect for frame 1.
# Now for frame 2 at 5643: the tx_start must be pulsed 3 cycles before the tick.
# With warmup=3, ticks are at 430, 864, ..., 430+434*k.
# 5643 = 430 + 434*k? 5213/434 = 12.007. Not exact.
# 
# Maybe the inter-frame gap means the baud_gen was reset between frames?
# Or maybe the tx_start for frame 2 is at a different offset.
# 
# Let me try: after frame 1, continue running with tx_start=0 and find when
# the model is in IDLE. Then pulse tx_start at the right time to get frame 2
# starting at 5643.

tx = UartTx()
tx.reset()
tx.step(1, 1, 1, 60)  # warmup -3
tx.step(1, 1, 0, 0)   # warmup -2
tx.step(1, 1, 0, 0)   # warmup -1

# Run until we find where frame 2 should start
# We need tx_out=0 at vec 5643. 
# The model will be in IDLE after frame 1 (tx_done at 4336).
# We need to pulse tx_start such that the next baud tick is at 5643.
# Ticks at: 430+434*k. We need 430+434*k = 5643. k = (5643-430)/434 = 12.007. Not integer.
# 
# So 5643 is NOT a baud tick position. This means the frame 2 start doesn't align
# with the continuous baud_gen. 
# 
# Maybe the vector generation RESET the baud_gen between frames?
# Or maybe the vector generation used a different approach entirely.
#
# Let me check: what if the vector generation ran the RTL (not the golden model)?
# The RTL baud_gen is registered (tick on posedge), so the tick appears one cycle
# later than the golden model. Let me check with the RTL timing.
#
# RTL baud_gen: cnt counts 0,1,...,433. At cnt=433 (posedge), tick<=1.
# So tick is visible AFTER the posedge at cycle 433. In the TB, if we check
# after posedge, tick=1 at cycle 433. Same as golden model.
#
# Actually, the RTL has baud_tick as a registered output. So:
# cycle 0: cnt=0, posedge -> cnt<=1, tick<=0
# cycle 432: cnt=432, posedge -> cnt<=433, tick<=0
# cycle 433: cnt=433, posedge -> cnt<=0, tick<=1
# So tick=1 is visible from cycle 433 onwards (after the posedge at cycle 433).
# The uart_tx sees tick=1 at cycle 433 and transitions.
# 
# This is the same as the golden model. So the timing should be the same.
#
# Let me try a completely different approach: maybe the vector generation
# applied tx_start at specific cycles that we need to discover.
# Let me run the golden model and try pulsing tx_start at every possible
# cycle to find which one makes frame 2 start at 5643.

# After frame 1 ends at 4336, the model is in IDLE.
# We need to pulse tx_start at cycle X such that the next baud tick after X
# is at cycle 5643. 
# Ticks at: 430+434*k. The tick just before 5643 is at 430+12*434=5638.
# The tick after is at 430+13*434=6072.
# If tx_start is latched at cycle X, the next tick at or after X triggers the frame.
# For the frame to start at 5643, we need a tick at 5643. But 5643 is not a tick.
#
# UNLESS the baud_gen was reset. If we reset the baud_gen at some point,
# the tick count restarts. 
#
# Let me check: what if the vector generation reset the entire uart_tx between frames?
# Then the baud_gen restarts from 0, and the first tick is at cycle 433 after reset.
# Frame 2 starts at 5643. If reset at 5643-433=5210, then first tick at 5643.
# But that would mean tx_start is latched during reset, which doesn't work.
# 
# If reset at 5643-430=5213 (with 3 warmup), then:
# reset at 5213, warmup 3 cycles (5213,5214,5215) with tx_start=1 at 5213,
# first tick at 5213+430=5643. Frame starts at 5643. Match!
#
# So the vector generation RESET the uart_tx between frames and used 3-warmup!
# Let me verify: reset at 5213, warmup 3, tx_start=1 at 5213, data=255.
# Frame 2 at 5643. 5643-5213=430. With 3 warmup, first tick at 430. Match!

# Let me check the inter-frame gaps:
# Frame 1 ends at 4336. Frame 2 reset at 5213. Gap = 5213-4336 = 877 = 2*434 + 9.
# Frame 2 ends at 9549. Frame 3 reset at 9549+877=10426? Frame 3 starts at 10856.
# 10856-10426=430. Yes! 3 warmup gives first tick at 430.
# 
# Frame 3 ends at 14762. Frame 4 reset at 14762+877=15639. Frame 4 starts at 16069.
# 16069-15639=430. Yes!
#
# So the pattern is: reset + 3 warmup cycles (tx_start=1 at first warmup) before each frame.
# Reset cycles: 5213, 10426, 15639 (frame 1 reset is at -3, i.e., warmup before vec 0)
# 
# But wait, the vector file shows rst_n=1 for all vectors. So the reset isn't via rst_n.
# Maybe the vector generation used a different reset mechanism.
# 
# Actually, let me reconsider. Maybe the baud_gen is NOT reset between frames,
# but the tx_start is pulsed at a cycle that aligns with a tick.
# 
# Let me check: is 5643 a tick if we DON'T reset? Ticks at 430+434*k.
# 430 + 434*12 = 5638. 430 + 434*13 = 6072. 5643 is between them. Not a tick.
#
# So the baud_gen MUST have been reset between frames. But rst_n=1 in all vectors.
# 
# Hmm, let me look at the actual vector data around the frame boundaries more carefully.
for i in range(4330, 4345):
    print(f"vec {i}: {data['vectors'][i]['expected']}")
print("---")
for i in range(5638, 5650):
    print(f"vec {i}: {data['vectors'][i]['expected']}")