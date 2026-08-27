import json
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# The expected outputs at 5210-5215 are all tx_out=1 (idle). 
# If we reset at 5210 (rst_n=0), the RTL produces tx_out=1 (reset value). Match!
# Then at 5213, we deassert reset and pulse tx_start=1.
# 
# Let me verify the full approach:
# Frame 1: 3 warmup before vec 0 (no reset, rst_n=1, tx_start=1 at -3)
# Frame 2: reset at 5210 (rst_n=0 for 3 cycles), tx_start=1 at 5213, data=255
# Frame 3: reset at 10423, tx_start=1 at 10426, data=165
# Frame 4: reset at 15636, tx_start=1 at 15639, data=0
# Last vec 20852: rst_n=0 (reset)

# Reset cycles: 5210-5212, 10423-10425, 15636-15638
# tx_start cycles: -3 (before vec 0), 5213, 10426, 15639

# Let me verify with the golden model
tx = UartTx()
tx.reset()

# Warmup for frame 1: 3 cycles with tx_start=1 at first
tx.step(1, 1, 1, 60)  # warmup -3
tx.step(1, 1, 0, 0)   # warmup -2
tx.step(1, 1, 0, 0)   # warmup -1

# Reset + tx_start schedule
reset_cycles = set(range(5210, 5213)) | set(range(10423, 10426)) | set(range(15636, 15639))
txstart_cycles = {5213: 255, 10426: 165, 15639: 0}
# Also the final reset at 20852
reset_cycles.add(20852)

mismatches = 0
for i in range(len(data['vectors'])):
    exp = data['vectors'][i]['expected']
    if i in reset_cycles:
        out, done = tx.step(1, 0, 0, 0)  # reset
    elif i in txstart_cycles:
        out, done = tx.step(1, 1, 1, txstart_cycles[i])  # tx_start pulse
    else:
        out, done = tx.step(1, 1, 0, 0)
    if out != exp.get('tx_out', 1) or done != exp.get('tx_done', 0):
        mismatches += 1
        if mismatches <= 5:
            print(f"vec {i}: MISMATCH out={out} done={done} exp={exp}")
print(f"ALL {len(data['vectors'])} vecs: {mismatches} mismatches")