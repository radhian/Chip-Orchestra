import json
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# Frame data: [60, 255, 165, 0]
# Frame starts: [430, 5643, 10856, 16069]
# tx_start pulse: 3 cycles before each frame start
# tx_start at: 427, 5640, 10853, 16066
# But vec 0 is the first recorded vector. The first tx_start at 427 is BEFORE vec 0,
# so it's in the warmup (3 warmup cycles: -3, -2, -1 = vecs 427, 428, 429 if we 
# think of vec 0 as cycle 430... no, vec 0 is cycle 0).
# 
# Actually, the warmup is 3 cycles before vec 0. The first frame starts at vec 430.
# tx_start at vec 430-3=427. But 427 > 0, so it's within the recorded range!
# But the vector file shows tx_start=0 at vec 427. So the vector file is wrong.
#
# Let me re-examine. Maybe the warmup is longer. Let me check:
# If tx_start=1 at vec 0 (first recorded vector), first baud tick at vec 433.
# Frame start at 433. But vector shows frame start at 430. Diff=3.
# 
# If tx_start=1 at vec -3 (warmup), first baud tick at vec 430. Frame start at 430. Match!
# So warmup = 3 cycles, tx_start=1 at warmup cycle 0 (vec -3).
# 
# For frame 2: starts at 5643. tx_start at 5643-3=5640.
# But the vector file shows tx_start=0 at vec 5640. So the vector generation
# applied tx_start=1 at vec 5640 but recorded it as 0.
#
# For the TB, we need to drive tx_start=1 at the right cycles.
# Let me verify: drive tx_start=1 at warmup, then at 5640, 10853, 16066.

tx = UartTx()
tx.reset()
# Warmup: 3 cycles with tx_start=1 at first
tx.step(1, 1, 1, 60)   # warmup cycle -3
tx.step(1, 1, 0, 0)    # warmup cycle -2
tx.step(1, 1, 0, 0)    # warmup cycle -1

# tx_start pulse cycles (0-indexed from vec 0)
pulse_cycles = {5640: 255, 10853: 165, 16066: 0}

mismatches = 0
for i, v in enumerate(data['vectors']):
    exp = v['expected']
    ts = 1 if i in pulse_cycles else 0
    din = pulse_cycles.get(i, 0)
    out, done = tx.step(1, 1, ts, din)
    if out != exp.get('tx_out', 1) or done != exp.get('tx_done', 0):
        mismatches += 1
        if mismatches <= 10:
            print(f"vec {i}: MISMATCH out={out} done={done} exp={exp}")
print(f"ALL {len(data['vectors'])} vecs: {mismatches} mismatches")