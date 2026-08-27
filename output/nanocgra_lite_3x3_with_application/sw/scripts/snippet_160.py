import json
import sys
sys.path.insert(0, 'golden')
from model.uart_rx import UartRx

with open('golden/vectors/uart_rx.json') as f:
    data = json.load(f)

# rx_valid=1 at: 3905, 8246, 12587, 16928
# rx_byte at: 4340(165), 8681(0), 13022(255), 17363(60)
# 
# The rx_valid pulses at 3905, and rx_byte=165 appears at 4340.
# 4340-3905=435. That's ~1 baud period. 
# Actually, rx_valid pulses when the 8th data bit is sampled.
# rx_byte is updated at the same time as rx_valid. But the vector shows
# rx_byte at 4340, not 3905. Let me check: at 3905, rx_valid=1 but rx_byte
# is not in the expected (meaning it's the default/old value).
# At 4340, rx_byte=165 but rx_valid=0.
# 
# In the golden model: when bit_idx==8, rx_byte=shreg, rx_valid=1.
# So rx_byte and rx_valid update in the same step.
# But the vector shows them at different cycles. This might be because
# the vector generation only records CHANGED values.
# 
# At 3905: rx_valid changes 0->1 (recorded). rx_byte changes 0->165 (NOT recorded?).
# At 3906: rx_valid changes 1->0 (recorded).
# At 4340: rx_byte is 165 (but it was already 165 since 3905). 
# Wait, maybe rx_byte was 0 until 4340. Let me check the golden model.
# 
# In the golden model UartRx.step():
#   when bit_idx==8: rx_byte=shreg, rx_valid=1
# So rx_byte updates at the same cycle as rx_valid.
# But the vector at 3905 doesn't include rx_byte. Maybe the vector generation
# only includes CHANGED outputs, and rx_byte didn't change at 3905 because
# it was already 165 from a previous frame? No, the first frame should set it.
#
# Actually, looking at the vector format: each vector's "expected" only includes
# the outputs that CHANGED from the previous vector. So at 3905, rx_valid changed
# 0->1, but rx_byte might have changed too but wasn't recorded.
# 
# Let me check: what is rx_byte at vec 3904?
print(f"vec 3904: {data['vectors'][3904]['expected']}")
print(f"vec 3905: {data['vectors'][3905]['expected']}")
print(f"vec 3906: {data['vectors'][3906]['expected']}")
print(f"vec 4340: {data['vectors'][4340]['expected']}")

# The expected at 3905 only has rx_valid=1. rx_byte is not mentioned.
# This could mean rx_byte is either 0 (default) or unchanged.
# At 4340, rx_byte=165 is explicitly mentioned.
# 
# In the golden model, rx_byte is set when rx_valid=1 (at 3905).
# So rx_byte=165 at 3905. But the vector doesn't record it.
# At 4340, rx_byte is still 165 (unchanged since 3905). Why is it recorded at 4340?
# 
# Maybe the vector generation records rx_byte when it's first set AND when it's
# read back. Or maybe the vector generation has a different timing for rx_byte.
# 
# Let me run the golden model and check.
rx = UartRx()
rx.reset()

# The uart_rx has rx_in=0 for the first ~3900 vectors. Let me check what stimulus
# produces rx_valid=1 at vec 3905.
# 
# rx_in=0 for vecs 0..3904 (all 0). Then rx_in=1 at 3905.
# But the UART frame starts with a start bit (0). If rx_in=0 for 3900 cycles,
# the receiver would detect a start bit immediately and start sampling.
# 
# Let me check: the first baud tick is at 433 (with no warmup) or 430 (with 3 warmup).
# If rx_in=0 from vec 0, the receiver sees a falling edge at the first tick.
# With 3 warmup: first tick at 430. prev_line=1 (idle), rx_in=0 -> start bit detected.
# Then 8 data bits sampled at ticks 864, 1298, ..., 3902. All rx_in=0 -> byte=0.
# rx_valid=1 at tick 3902 (bit7 sampled). But vector shows rx_valid=1 at 3905.
# 3905-3902=3. Off by 3.
# 
# With no warmup: first tick at 433. Start at 433. Data at 867, 1301, ..., 3905.
# rx_valid=1 at 3905 (bit7 at tick 3905). Match!
# 
# So uart_rx vectors were generated with NO warmup (0 warmup cycles).
# First tick at 433. Start bit detected at 433. Data bits at 867, 1301, ..., 3905.
# All rx_in=0 -> byte=0x00. rx_valid=1 at 3905.
# 
# But the vector at 3905 doesn't show rx_byte. And at 4340, rx_byte=165.
# 4340-3905=435. 4340 is the next tick after 3905 (3905+434=4339, not 4340).
# 4340 = 433 + 9*434 = 433 + 3906 = 4339. Not 4340.
# 4340 = 433 + 10*434 = 433 + 4340 = 4773. No.
# 
# Hmm, let me recalculate. With no warmup, ticks at 433+434*k.
# k=0: 433, k=1: 867, k=2: 1301, ..., k=8: 3905, k=9: 4339.
# rx_valid=1 at k=8 (vec 3905). rx_byte set at 3905.
# At k=9 (vec 4339): stop bit sampled. rx_valid=0.
# 
# But rx_byte=165 at vec 4340. 4340 is not a tick (4339 is). Off by 1.
# 
# Maybe the vector generation used the RTL timing (registered baud_tick).
# In the RTL, baud_tick is registered, so the uart_rx sees it one cycle later.
# RTL: tick at cycle 433 (registered). uart_rx sees tick at cycle 434.
# So effective ticks at 434+434*k.
# k=0: 434, k=1: 868, ..., k=8: 3906, k=9: 4340.
# rx_valid=1 at k=8 (vec 3906). But vector shows 3905. Off by 1.
# 
# Hmm. Let me try with the golden model and no warmup.
rx = UartRx()
rx.reset()
mismatches = 0
for i in range(len(data['vectors'])):
    inp = data['vectors'][i]['inputs']
    exp = data['vectors'][i]['expected']
    byte_val, valid = rx.step(inp['clk'], inp['rst_n'], inp['rx_in'])
    # Check: rx_valid
    exp_valid = exp.get('rx_valid', None)
    exp_byte = exp.get('rx_byte', None)
    if exp_valid is not None and valid != exp_valid:
        mismatches += 1
        if mismatches <= 5:
            print(f"vec {i}: valid MISMATCH model={valid} exp={exp_valid}")
    if exp_byte is not None and byte_val != exp_byte:
        mismatches += 1
        if mismatches <= 5:
            print(f"vec {i}: byte MISMATCH model={byte_val} exp={exp_byte}")
print(f"ALL {len(data['vectors'])} vecs: {mismatches} mismatches")