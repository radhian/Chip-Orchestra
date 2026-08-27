import json
import sys
sys.path.insert(0, 'golden')
from model.uart_rx import UartRx

with open('golden/vectors/uart_rx.json') as f:
    data = json.load(f)

# The mismatches are at vecs 8245/8246, 12585/12587, 16925/16928.
# The model produces rx_valid=1 at 8245, but the vector expects it at 8246 (off by 1).
# The model produces rx_valid=1 at 12585, but the vector expects it at 12587 (off by 2).
# The model produces rx_valid=1 at 16925, but the vector expects it at 16928 (off by 3).
# 
# The offset increases: 0 (first frame at 3905 matches), 1, 2, 3.
# This suggests the baud_gen drifts by 1 cycle per frame.
# 
# This is likely because the vector generation used the RTL's registered baud_gen
# which has a 1-cycle pipeline delay. Each frame, the start bit detection is off by 1.
# 
# Actually, the increasing offset suggests the vector generation reset the model
# between frames (like uart_tx), with different warmup lengths.
# 
# Frame 1: rx_valid at 3905. Model matches (0 warmup, first tick at 433).
# Frame 2: rx_valid at 8246. Model gives 8245. Off by 1.
# Frame 3: rx_valid at 12587. Model gives 12585. Off by 2.
# Frame 4: rx_valid at 16928. Model gives 16925. Off by 3.
# 
# The increasing offset (0, 1, 2, 3) suggests the baud_gen was reset between frames
# with 1, 2, 3 warmup cycles respectively. Or the reset happened at different offsets.
# 
# Let me check: if the model is reset at certain cycles, the baud_gen restarts.
# Frame 2: rx_valid at 8246. If reset at 8246-433*9=8246-3897=4349.
# With 0 warmup: first tick at 4349+433=4782. Start at 4782. Data at 5216, ..., 8246.
# 8246-4782=3464=8*434.0. Yes! 8 data bits, rx_valid at 8246. Match!
# 
# But the vector file shows rst_n=1 at 4349. So the reset isn't via rst_n.
# 
# Let me check the rx_in pattern to understand the frame structure.
# Frame 1: rx_in=0 from vec 0 to ~3905. Start bit at tick 433. All data bits=0. Byte=0.
# But rx_byte=165 at vec 4340. 165=0xA5=10100101. That's not all zeros.
# 
# Wait, the rx_in values change over time. Let me look at the rx_in pattern.
# Find where rx_in changes.
rx_in_changes = []
prev_rx_in = None
for i in range(len(data['vectors'])):
    rx_in = data['vectors'][i]['inputs']['rx_in']
    if rx_in != prev_rx_in:
        rx_in_changes.append((i, rx_in))
        prev_rx_in = rx_in
print(f"rx_in changes ({len(rx_in_changes)}):")
for c in rx_in_changes[:50]:
    print(f"  vec {c[0]}: rx_in={c[1]}")