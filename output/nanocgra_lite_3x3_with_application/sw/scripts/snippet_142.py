import json
# ALL uart_tx vectors have tx_start=0, data_in=0, yet the expected tx_out changes.
# This means the vector file was generated with a stimulus that included tx_start=1
# at some point, but the recorded inputs don't show it. OR the vectors were generated
# by running the golden model with an internal tx_start pulse that isn't recorded.
# 
# Let me check: the first transition is at vec 430 where tx_out goes 1->0 (start bit).
# If tx_start was pulsed at vec 0 (the first vector), then:
# - baud_gen counts 434 cycles per bit
# - At vec 0: tx_start=1 (but recorded as 0?), start_req latched
# - At first baud tick (vec 433 or 434): IDLE->START, tx_out=0
# That would put the start bit at ~vec 434. The vector shows tx_out=0 at vec 430.
# Close but not exact.
#
# Actually, let me re-examine. The golden model UartTx latches tx_start on ANY clock.
# If the vector generation pulsed tx_start=1 at vec 0 but recorded it as 0, that's a
# vector file bug. But the expected outputs reflect the actual stimulus.
#
# The problem: the TB can only drive what the vector file says. If tx_start=0 for all
# vectors, the RTL will never transmit, and tx_out will stay 1. So the TB will fail
# on every vector where tx_out=0 is expected.
#
# This is a fundamental issue with the uart_tx vector file. Let me check if maybe
# the vectors are meant to be driven with a tx_start pulse that we need to infer.
#
# Let me look at the pattern: tx_out goes 0 at vec 430, back to 1 at vec 1732,
# 0 at 3468, 1 at 4336 (with tx_done=1). That's a full frame:
# start(0) + 8 data bits + stop(1) = 10 bits * 434 = 4340 cycles.
# vec 430 to vec 4336 = 3906 cycles. Hmm, 9*434=3906. So 9 bits from 430 to 4336.
# Actually start bit at 430, then 8 data bits, then stop at 430+9*434=4336.
# So the frame starts at vec 430.
#
# If tx_start was pulsed at vec 0, the baud_gen first tick is at vec 433 (0-indexed).
# At vec 433: IDLE sees start_req, goes to START, tx_out=0. But vector shows tx_out=0
# at vec 430. Off by 3.
#
# Let me check the baud_gen timing more carefully.
import sys
sys.path.insert(0, 'golden')
from model.baud_gen import BaudGen

bg = BaudGen()
bg.reset()
ticks = []
for i in range(440):
    t = bg.step(1, 1)
    if t:
        ticks.append(i)
print(f"First 3 baud ticks at vecs: {ticks[:3]}")
print(f"div={bg.div}")