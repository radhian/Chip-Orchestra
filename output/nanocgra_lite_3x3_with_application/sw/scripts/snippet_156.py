import json
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# 41 mismatches. The reset at 5210-5212 resets the baud_gen.
# After reset at 5213, tx_start=1. baud_gen starts at 5213.
# First tick at 5213+433=5646. But frame 2 starts at 5643. Off by 3.
# 
# The issue: after reset, the baud_gen starts from cnt=0.
# With 3 warmup cycles (5213, 5214, 5215), cnt at 5216 = 3.
# First tick at 5216+430=5646. But frame 2 starts at 5643.
# 
# Wait, the golden model: reset() sets cnt=0. Then step(1,1,1,255) at 5213:
# cnt=0, not at div-1, cnt->1, tick=0. step at 5214: cnt=1->2. step at 5215: cnt=2->3.
# vec 5216: cnt=3->4. ... vec 5646: cnt=433->0, tick=1. 
# 5646-5213=433. So first tick at 5646. But frame 2 starts at 5643. Off by 3.
#
# The 3-cycle offset means the warmup needs to be 0 cycles, not 3.
# If tx_start=1 at 5210 (right after reset starts), and reset is only 1 cycle:
# reset at 5210 (rst_n=0), then rst_n=1 at 5211 with tx_start=1.
# baud_gen starts at 5211. First tick at 5211+433=5644. Still off by 1.
#
# Or: reset at 5210, rst_n=1 at 5210 (same cycle), tx_start=1 at 5210.
# But the golden model: if rst_n=0, it resets and returns. If rst_n=1, it runs.
# Can't do both in one cycle.
#
# Let me try: NO reset between frames. Just pulse tx_start at the right cycle.
# The baud_gen runs continuously. Ticks at 430+434*k.
# Frame 2 at 5643. We need a tick at 5643. 5643-430=5213. 5213/434=12.007. Not a tick.
#
# What if the first frame's tick is at 433 (not 430)?
# Then ticks at 433+434*k. 5643-433=5210. 5210/434=12.0. Yes!
# 433+12*434=433+5208=5641. Not 5643. Off by 2.
#
# What if ticks at 431+434*k? 5643-431=5212. 5212/434=12.009. No.
# What if ticks at 432+434*k? 5643-432=5211. 5211/434=12.006. No.
# What if ticks at 434+434*k? 5643-434=5209. 5209/434=12.0. Yes!
# 434+12*434=434+5208=5642. Not 5643. Off by 1.
#
# None of these work exactly. Let me check the EXACT tick positions by looking
# at where tx_out changes in the vector file.

# Find all transitions in the first 10000 vectors
transitions = []
prev_out = 1
for i in range(min(10000, len(data['vectors']))):
    exp = data['vectors'][i]['expected']
    out = exp.get('tx_out', 1)
    done = exp.get('tx_done', 0)
    if out != prev_out or done == 1:
        transitions.append((i, out, done))
    prev_out = out
print("Transitions in first 10000 vecs:")
for t in transitions:
    print(f"  vec {t[0]}: tx_out={t[1]}, tx_done={t[2]}")
    if t[2] == 1:
        # Calculate tick positions within this frame
        pass

# Calculate inter-transition gaps
print("\nGaps:")
for i in range(1, len(transitions)):
    gap = transitions[i][0] - transitions[i-1][0]
    print(f"  {transitions[i-1][0]} -> {transitions[i][0]}: gap={gap} ({gap/434:.2f} baud)")