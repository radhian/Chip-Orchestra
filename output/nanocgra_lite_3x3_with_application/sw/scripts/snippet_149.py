import json
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# Frame 2 starts at 5643 but our tx_start at 5640 didn't trigger it.
# The issue: after frame 1 ends at 4336 (tx_done=1), the model goes to IDLE.
# Then at 5640, tx_start=1 is latched. Next baud tick after 5640...
# Baud ticks with 3-warmup: 430, 864, ..., 430+434*k
# 5640 = 430 + 12.0*434 = 430 + 5208 = 5638. Not exact.
# Let me find the actual baud tick positions.
# The baud_gen counts 0..433, ticks at 433, then 433+434=867, etc.
# With 3 warmup cycles, the first tick is at vec 430 (cnt=433 at vec 430).
# Subsequent ticks: 430+434=864, 864+434=1298, ...
# 5640: is it a tick? 5640-430=5210. 5210/434=12.004. Not a tick.
# Next tick after 5640: 430+13*434=430+5642=6072. 
# So tx_start at 5640, next tick at 6072. Frame would start at 6072, not 5643.
# That's way off.
#
# Maybe the tx_start for frame 2 is at a different position.
# Frame 2 starts at 5643. If the start bit appears at the baud tick,
# the tick is at 5643. 5643-430=5213. 5213/434=12.0. Yes! 430+12*434=430+5208=5638.
# Hmm, 5638 != 5643. 
#
# Wait, let me recalculate. 430 + 12*434 = 430 + 5208 = 5638. Not 5643.
# 5643 - 430 = 5213. 5213 / 434 = 12.0069. Not exact.
#
# Let me check if the inter-frame gap affects the baud_gen.
# After frame 1 ends at 4336, the baud_gen continues running.
# The ticks continue at 430+434*k regardless of the TX state.
# So ticks at: 430, 864, 1298, ..., 430+434*k
# Frame 2 start at 5643. Is 5643 = 430 + 434*k? 5643-430=5213. 5213/434=12.007. No.
# 
# Hmm. Let me check if the first frame's start is really at a tick.
# Maybe the 3-warmup isn't exactly right. Let me try different warmup lengths.

for warmup in range(0, 10):
    tx = UartTx()
    tx.reset()
    for w in range(warmup):
        ts = 1 if w == 0 else 0
        tx.step(1, 1, ts, 60)
    
    # Find when tx_out first goes 0
    for i in range(1000):
        out, done = tx.step(1, 1, 0, 0)
        if out == 0:
            print(f"warmup={warmup}: first tx_out=0 at vec {i}")
            break