import json
# The RTL baud_gen is registered: baud_tick is a reg, set on posedge clk.
# So baud_tick=1 appears one cycle AFTER cnt reaches BAUD_DIV-1.
# The golden model is combinational: tick=1 in the same step when cnt==div-1.
# 
# RTL: cnt starts at 0. 
#   cycle 0: cnt=0 -> cnt<=1, tick<=0
#   cycle 1: cnt=1 -> cnt<=2, tick<=0
#   ...
#   cycle 432: cnt=432 -> cnt<=433, tick<=0
#   cycle 433: cnt=433(=434-1) -> cnt<=0, tick<=1
#   cycle 434: cnt=0 -> cnt<=1, tick<=0
# So first tick at cycle 433 (after 433 posedges). Same as golden model.
#
# But the uart_tx vector shows the start bit at vec 430, not 433.
# Let me check if the uart_tx vectors were generated with a 3-cycle head start.
# 
# Actually, let me look at this differently. The uart_tx vectors have 20853 entries.
# 20853 / 434 = 48.04. So about 48 baud periods.
# The transitions are at: 430, 1732, 3468, 4336, 5643, 6077, 9549, ...
# 
# Let me check: 430 = 434 - 4. So the start bit appears at cycle 430, which is
# 4 cycles before the first baud tick at 433. That doesn't make sense for the
# golden model or the RTL.
#
# UNLESS the vector generation applied tx_start at cycle -3 (before recording started),
# and the baud_gen had already been running for 3 cycles. Then:
# - cycle -3: tx_start=1, start_req latched. baud_gen cnt=0
# - cycle -2: cnt=1
# - cycle -1: cnt=2
# - cycle 0: cnt=3 (first recorded vector)
# - cycle 430: cnt=433=434-1 -> tick=1 (golden model) or tick at 431 (RTL registered)
#
# Hmm, with golden model: tick at cycle 430 (cnt=430+3=433=div-1). Yes!
# If the baud_gen started 3 cycles before vec 0, then at vec 430, cnt=433=div-1,
# tick=1 (golden model, combinational). The uart_tx sees the tick and goes IDLE->START,
# tx_out=0. That matches vec 430!
#
# So the vector generation:
# 1. Started the model 3 cycles before recording
# 2. Pulsed tx_start=1 at cycle -3 (before recording)
# 3. Recorded from cycle 0 onwards with tx_start=0
#
# This means the TB CANNOT reproduce these vectors by driving tx_start=0.
# The TB needs to pulse tx_start=1 BEFORE the vector loop starts, and run 3 warmup cycles.
#
# But we don't know the exact data_in value or the warmup length.
# Let me figure out the data byte from the transitions.
# 
# With 3-cycle head start, baud ticks at vecs: 430, 864, 1298, 1732, 2166, 2600, 3034, 3468, 3902, 4336
# (each 434 apart starting from 430)
# 
# Frame: 
# vec 430: tick -> IDLE->START, tx_out=0 (start bit)
# vec 864: tick -> START->DATA, tx_out=bit0
# vec 1298: tick -> DATA, tx_out=bit1
# vec 1732: tick -> DATA, tx_out=bit2
# vec 2166: tick -> DATA, tx_out=bit3
# vec 2600: tick -> DATA, tx_out=bit4
# vec 3034: tick -> DATA, tx_out=bit5
# vec 3468: tick -> DATA, tx_out=bit6
# vec 3902: tick -> DATA, tx_out=bit7
# vec 4336: tick -> STOP, tx_out=1, tx_done=1
#
# Wait, that's 10 ticks for start+8data+stop. But the golden model:
# IDLE: on tick, if start_req: go START, tx_out=0
# START: on tick, tx_out=bit0, go DATA
# DATA: on tick, tx_out=bit[bit_idx], bit_idx++
#   when bit_idx==8: go STOP
# STOP: on tick, tx_out=1, tx_done=1, go IDLE
#
# So:
# tick 430: IDLE->START, tx_out=0
# tick 864: START->DATA, tx_out=shreg[0]=bit0, bit_idx=1
# tick 1298: DATA, tx_out=shreg[1]=bit1, bit_idx=2
# tick 1732: DATA, tx_out=shreg[2]=bit2, bit_idx=3
# tick 2166: DATA, tx_out=shreg[3]=bit3, bit_idx=4
# tick 2600: DATA, tx_out=shreg[4]=bit4, bit_idx=5
# tick 3034: DATA, tx_out=shreg[5]=bit5, bit_idx=6
# tick 3468: DATA, tx_out=shreg[6]=bit6, bit_idx=7
# tick 3902: DATA, tx_out=shreg[7]=bit7, bit_idx=8 -> STOP
# tick 4336: STOP, tx_out=1, tx_done=1 -> IDLE
#
# Vector transitions: 430(0), 1732(1), 3468(0), 4336(1,done)
# So:
# 430: tx_out=0 (start)
# 864: tx_out=bit0 (no transition if bit0=0)
# 1298: tx_out=bit1 (no transition if bit1=0)
# 1732: tx_out=bit2=1 (transition 0->1)
# 2166: tx_out=bit3 (no transition if bit3=1)
# 2600: tx_out=bit4 (no transition if bit4=1)
# 3034: tx_out=bit5 (no transition if bit5=1)
# 3468: tx_out=bit6=0 (transition 1->0)
# 3902: tx_out=bit7 (no transition if bit7=0)
# 4336: tx_out=1 (transition 0->1, stop, done)
#
# So: bit0=0, bit1=0, bit2=1, bit3=1, bit4=1, bit5=1, bit6=0, bit7=0
# byte = 0*1 + 0*2 + 1*4 + 1*8 + 1*16 + 1*32 + 0*64 + 0*128 = 4+8+16+32 = 60 = 0x3C
#
# So data_in=0x3C=60, tx_start pulsed 3 cycles before vec 0.
# 
# Let me verify this with the golden model.
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

tx = UartTx()
tx.reset()
# 3 warmup cycles with tx_start=1 at cycle -3
# Actually, let me try: tx_start=1 at the first warmup cycle, data_in=60
# warmup: cycle -3: tx_start=1, data_in=60
#          cycle -2: tx_start=0
#          cycle -1: tx_start=0
# then record from cycle 0

# Run 3 warmup cycles
tx.step(1, 1, 1, 60)  # cycle -3: tx_start=1
tx.step(1, 1, 0, 0)   # cycle -2
tx.step(1, 1, 0, 0)   # cycle -1

mismatches = 0
for i, v in enumerate(data['vectors'][:5000]):
    inp = v['inputs']
    exp = v['expected']
    out, done = tx.step(1, 1, 0, 0)  # tx_start=0 as recorded
    if out != exp.get('tx_out', 1) or done != exp.get('tx_done', 0):
        mismatches += 1
        if mismatches <= 5:
            print(f"vec {i}: MISMATCH out={out} done={done} exp={exp}")
print(f"First 5000 vecs: {mismatches} mismatches")