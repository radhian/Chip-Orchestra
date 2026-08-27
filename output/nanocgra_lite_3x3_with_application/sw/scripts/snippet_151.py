import json
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx
from model.baud_gen import BaudGen

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# The tx_out goes 0 at vec 5643. Between frames (4337 to 5642), tx_out=1 (idle).
# Frame 2 start at 5643. If the baud_gen was NOT reset, ticks at 430+434*k.
# 5643 is not a tick. So either:
# 1. The baud_gen was reset between frames, OR
# 2. The vector generation used a different mechanism
#
# Let me try approach: the vector generation used the RTL simulation where
# the baud_gen is registered (tick appears 1 cycle later).
# RTL baud_gen: at posedge with cnt=433, tick<=1. So tick=1 is visible
# starting from the NEXT cycle check. In a TB that checks after posedge:
# cycle 433: cnt was 433 at posedge, tick becomes 1. Check after posedge: tick=1.
# This is the same as golden model.
#
# Wait, maybe the issue is that the RTL uart_tx latches tx_start on ANY clock
# (not just on baud tick). So if tx_start is pulsed between ticks, it's latched.
# The next tick triggers the transmission.
# 
# Let me try: tx_start=1 at vec 5640 (3 cycles before 5643).
# With continuous baud_gen (no reset), ticks at 430+434*k.
# The tick at 430+12*434=5638. tx_start at 5640 is AFTER tick 5638.
# Next tick at 430+13*434=6072. So frame would start at 6072, not 5643.
# That's 429 cycles off. Doesn't work.
#
# Let me try: what if the baud_gen divider is different? 
# 5643-430=5213. If div=434, 5213/434=12.007. Not integer.
# If the first frame used div=434 but the tick at 430, and the second frame
# also starts at a tick... 5643-430=5213. 5213/12=434.4. Not 434.
#
# What if the first tick is at 433 (not 430)? Then ticks at 433+434*k.
# 5643-433=5210. 5210/434=12.0. Yes! 433+12*434=433+5208=5641. Not 5643.
# 433+12*434=5641. Still off by 2.
#
# What if warmup=0 (no warmup)? First tick at 433. tx_start at 0.
# Frame 1 starts at 433. But vector shows 430. Off by 3.
#
# I'm going in circles. Let me try a brute-force approach: run the golden model
# with the RTL's registered baud_gen behavior and see if it matches.
# 
# Actually, let me look at this from a different angle. The uart_tx vectors have
# 20853 entries. Let me check if the LAST entry has rst_n=0 (reset at end).
print(f"Last vec: {data['vectors'][-1]}")
print(f"First vec: {data['vectors'][0]}")

# Check if any vec has rst_n=0
rst_vecs = [i for i, v in enumerate(data['vectors']) if v['inputs'].get('rst_n', 1) == 0]
print(f"Vectors with rst_n=0: {rst_vecs}")