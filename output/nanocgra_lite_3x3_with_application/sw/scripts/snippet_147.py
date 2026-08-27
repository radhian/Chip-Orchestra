import json
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# There are 4 frames ending at vecs 4336, 9549, 14762, 19975.
# Frame 1: ends at 4336, starts at 4336-9*434=4336-3906=430
# Frame 2: ends at 9549, starts at 9549-3906=5643
# Frame 3: ends at 14762, starts at 14762-3906=10856
# Frame 4: ends at 19975, starts at 19975-3906=16069
# 
# So frames start at: 430, 5643, 10856, 16069
# Gaps between frames: 5643-4336=1307, 10856-9549=1307, 16069-14762=1307
# 1307 = 3*434 + 5. Hmm, 1307/434 = 3.01. So ~3 baud periods between frames.
# 
# Each frame starts 3 cycles before a baud tick (like frame 1 at 430, tick at 433).
# Frame 2 starts at 5643. 5643+3=5646. Is 5646 a baud tick? 
# Baud ticks (with 3-cycle head start): 430, 864, ..., 430+434*k
# 5646-430 = 5216. 5216/434 = 12.02. Not exact.
# 
# Actually, the tx_start for frame 2 must have been pulsed 3 cycles before vec 5643,
# i.e., at vec 5640. But the vector file shows tx_start=0 at vec 5640.
# So the vector generation pulsed tx_start internally but didn't record it.
#
# This means the uart_tx vector file is fundamentally broken for TB generation:
# the inputs don't match the stimulus that produced the expected outputs.
# 
# The approach for the TB: we need to RECONSTRUCT the actual stimulus.
# We know:
# - 3 warmup cycles before vec 0, with tx_start=1, data_in=60
# - Then at some point before frame 2 (vec 5643), another tx_start pulse
# - Frame 2 starts at 5643, so tx_start at 5640, data_in=?
# 
# Let me figure out the data for each frame from the transitions.
# Frame 2: starts at 5643, ends at 9549.
# Transitions in frame 2: let me find them.

for frame_start, frame_end in [(430,4336), (5643,9549), (10856,14762), (16069,19975)]:
    transitions = []
    prev_out = 1  # idle high before start
    for i in range(frame_start, frame_end+1):
        exp = data['vectors'][i]['expected']
        out = exp.get('tx_out', 1)
        if out != prev_out:
            transitions.append((i, out))
        prev_out = out
    print(f"Frame [{frame_start}..{frame_end}]: transitions={transitions}")
    
    # Baud ticks within frame: frame_start, frame_start+434, ..., frame_start+9*434
    ticks = [frame_start + k*434 for k in range(10)]
    # tick 0: start bit (0)
    # tick 1: bit0, tick 2: bit1, ..., tick 8: bit7, tick 9: stop
    bits = []
    for k in range(1, 9):  # bit0..bit7
        tick_vec = frame_start + k*434
        out_at_tick = data['vectors'][tick_vec]['expected'].get('tx_out', 1)
        bits.append(out_at_tick)
    byte_val = sum(b << i for i, b in enumerate(bits))
    print(f"  data byte = 0x{byte_val:02X} = {byte_val}")