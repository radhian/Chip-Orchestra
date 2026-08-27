import json
# The baud_gen first tick is at vec 433 (0-indexed). But uart_tx shows tx_out=0 at vec 430.
# That's 3 cycles BEFORE the first baud tick. This doesn't match if tx_start was at vec 0.
#
# Let me check: maybe the uart_tx vectors were generated with a DIFFERENT baud_gen
# or the tx_start was pulsed at a different time.
#
# Actually, let me re-run the golden uart_tx model with tx_start=1 at vec 0 and see
# when tx_out first goes 0.
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# Run with tx_start=1 at vec 0, data_in=0xA5 (arbitrary)
tx = UartTx()
tx.reset()
transitions = []
for i in range(5000):
    ts = 1 if i == 0 else 0
    din = 0xA5 if i == 0 else 0
    out, done = tx.step(1, 1, ts, din)
    if i == 0:
        print(f"vec 0: tx_start=1, data_in=0xA5 -> tx_out={out}, tx_done={done}")
    if i > 0 and (out != prev_out or done != prev_done):
        transitions.append((i, out, done))
    prev_out = out
    prev_done = done
print(f"Transitions with tx_start@0, data=0xA5:")
for t in transitions[:10]:
    print(f"  vec {t[0]}: tx_out={t[1]}, tx_done={t[2]}")

# Now compare with the vector file transitions
print("\nVector file transitions:")
for i, v in enumerate(data['vectors'][:5000]):
    exp = v['expected']
    if i > 0:
        prev_exp = data['vectors'][i-1]['expected']
        if exp.get('tx_out', 1) != prev_exp.get('tx_out', 1) or exp.get('tx_done', 0) != prev_exp.get('tx_done', 0):
            print(f"  vec {i}: tx_out={exp.get('tx_out')}, tx_done={exp.get('tx_done')}")