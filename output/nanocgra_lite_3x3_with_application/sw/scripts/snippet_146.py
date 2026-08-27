import json
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# Now check ALL vectors with the 3-warmup approach
tx = UartTx()
tx.reset()
tx.step(1, 1, 1, 60)  # cycle -3: tx_start=1, data_in=60
tx.step(1, 1, 0, 0)   # cycle -2
tx.step(1, 1, 0, 0)   # cycle -1

mismatches = 0
for i, v in enumerate(data['vectors']):
    exp = v['expected']
    out, done = tx.step(1, 1, 0, 0)
    if out != exp.get('tx_out', 1) or done != exp.get('tx_done', 0):
        mismatches += 1
        if mismatches <= 10:
            print(f"vec {i}: MISMATCH out={out} done={done} exp={exp}")
print(f"ALL {len(data['vectors'])} vecs: {mismatches} mismatches")

# Check if there are multiple frames (multiple tx_start pulses)
# The vector file has 20853 entries. 20853/434 = 48.04 baud periods.
# One frame = 10 bits = 4340 cycles. 20853/4340 = 4.8 frames.
# So there should be ~4-5 frames. But we only pulsed tx_start once.
# Let me check where tx_done=1 appears (end of each frame)
done_vecs = []
for i, v in enumerate(data['vectors']):
    if v['expected'].get('tx_done', 0) == 1:
        done_vecs.append(i)
print(f"tx_done=1 at vecs: {done_vecs}")