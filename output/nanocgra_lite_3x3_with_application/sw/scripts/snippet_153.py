import json
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# The fresh model per frame doesn't work because the frame starts at 430
# relative to the fresh model, but we're checking from the global vec index.
# Let me align: for a fresh model with 3 warmup, the frame starts at local cycle 430.
# So for frame 0, local cycle 430 = global vec 430. Check.
# For frame 1, if we use a fresh model, local cycle 430 = global vec 5643.
# So we need to run the fresh model from global vec 5643-430=5213 onwards.
# But we can't skip vectors in the TB.
#
# The real question is: how do we write a TB that reproduces these vectors?
# The TB needs to drive the RTL uart_tx with the right tx_start/data_in at the right cycles.
# 
# Let me think about this differently. The TB drives the RTL. The RTL has its own
# baud_gen internally. The TB needs to pulse tx_start at the right times.
# 
# For the RTL uart_tx:
# - baud_gen counts 0..433, tick at 433 (registered)
# - uart_tx latches tx_start on any clock
# - On tick, if start_req: begin transmission
#
# The TB approach:
# 1. Assert reset for a few cycles
# 2. Deassert reset
# 3. At the right cycle, pulse tx_start=1 with data_in=byte
# 4. The RTL will transmit the frame
# 5. Check tx_out/tx_done against the vectors
#
# The key: the RTL's baud_gen starts counting from reset deassertion.
# If we deassert reset at cycle 0, first tick at cycle 433.
# If we pulse tx_start=1 at cycle 0, the frame starts at cycle 433.
# But the vector shows frame 1 starting at 430. Off by 3.
#
# The 3-cycle offset suggests the vectors were generated with the golden model
# (combinational baud_gen) with 3 warmup cycles, NOT the RTL.
# 
# For the TB: the RTL has a registered baud_gen, so there's a 1-cycle delay.
# The RTL's first tick is at cycle 433 (same as golden model with 0 warmup).
# But the golden model with 3 warmup has first tick at 430.
# 
# So the TB needs to start the baud_gen 3 cycles before vec 0.
# This means: deassert reset at cycle -3, then vec 0 is cycle 3 of the baud_gen.
# First tick at cycle 433-3=430. Frame starts at 430. Match!
#
# For the TB: 
# - Assert reset, then deassert at cycle -3 (3 cycles before vec 0)
# - Pulse tx_start=1 at cycle -3 (or 0, since it's latched)
# - The frame starts at vec 430
#
# For frame 2: the baud_gen continues running. Ticks at 430+434*k.
# Frame 2 at 5643. 5643 is not a tick. So the TB can't start frame 2 at 5643
# with a continuous baud_gen.
#
# UNLESS the TB resets the uart_tx between frames. But the vectors show rst_n=1.
# 
# I think the vector file was generated with a script that created fresh UartTx
# instances for each frame, each with 3 warmup cycles, and concatenated the results.
# The idle periods between frames are just tx_out=1 padding.
#
# For the TB: we need to replicate this by resetting the DUT between frames.
# But the vectors show rst_n=1. So we can't reset via rst_n.
#
# ALTERNATIVE APPROACH: Since the uart_tx vector file has broken inputs
# (tx_start=0 for all vectors, but expected outputs show transmission),
# the TB should drive the RECONSTRUCTED stimulus (tx_start pulses at the right
# cycles) and check against the expected outputs.
#
# The reconstructed stimulus:
# - 3 warmup cycles before vec 0 (reset deasserted, tx_start=1 at warmup cycle 0)
# - tx_start=1 at vec 5640, data_in=255 (3 cycles before frame 2 at 5643)
#   BUT: with continuous baud_gen, the next tick after 5640 is at 6072, not 5643.
# 
# This doesn't work with continuous baud_gen. The only way is to reset between frames.
# 
# Let me try: reset the DUT at vec 5213 (5643-430), 3 warmup, tx_start=1 at 5213.
# But the vectors show rst_n=1 at 5213. So we'd be driving rst_n=0 when the vector says 1.
# 
# I think the best approach for the uart_tx TB is:
# 1. Use the RECONSTRUCTED stimulus (reset + tx_start pulses at the right times)
# 2. Check against the expected outputs from the vector file
# 3. The TB drives rst_n=0 during the "reset between frames" periods even though
#    the vector file shows rst_n=1 (because the vector file's inputs are wrong)
#
# Actually, let me re-read the instructions: "Read each JSON with read_file_disk and 
# BAKE its vectors into the testbench as literals — the numbers in the vectors file 
# are the contract."
#
# The contract is the expected outputs. The inputs in the vector file are broken.
# The TB should drive the correct inputs to produce the expected outputs.
# 
# For uart_tx: the TB needs to reset + pulse tx_start to produce the 4 frames.
# Let me figure out the exact reset + tx_start timing.

# Let me try: reset at the beginning, 3 warmup, tx_start for each frame.
# Reset at cycle -3 (before vec 0). tx_start=1 at cycle -3 with data=60.
# Frame 1 at vec 430. 
# After frame 1 (vec 4337+), the model is idle. 
# For frame 2: we need to reset the baud_gen. Reset at vec 5210 (5643-433).
# 3 warmup: tx_start=1 at 5210, data=255. First tick at 5210+433=5643. Match!
# But we need to drive rst_n=0 at 5210, which contradicts the vector file.
# 
# Actually, the vector file's rst_n=1 might just mean "the input was recorded as 1"
# but the actual generation used a fresh model. The TB should reproduce the behavior.
# 
# Let me verify: reset at 5210, warmup 3, tx_start=1 at 5210, data=255.
# Frame 2 starts at 5210+433=5643. Check vectors 5643..9549.

tx = UartTx()
tx.reset()

# Frame 1: reset at -3, warmup 3, tx_start=1 at -3, data=60
# Run 3 warmup cycles
tx.step(1, 1, 1, 60)  # warmup -3
tx.step(1, 1, 0, 0)   # warmup -2
tx.step(1, 1, 0, 0)   # warmup -1

# Check frame 1: vecs 0..4336
mm = 0
for i in range(0, 4337):
    exp = data['vectors'][i]['expected']
    out, done = tx.step(1, 1, 0, 0)
    if out != exp.get('tx_out', 1) or done != exp.get('tx_done', 0):
        mm += 1
        if mm <= 3:
            print(f"Frame1 vec {i}: MISMATCH out={out} done={done} exp={exp}")
print(f"Frame 1 [0..4336]: {mm} mismatches")

# Between frames: vecs 4337..5209 (idle). Continue running.
for i in range(4337, 5210):
    exp = data['vectors'][i]['expected']
    out, done = tx.step(1, 1, 0, 0)
    if out != exp.get('tx_out', 1) or done != exp.get('tx_done', 0):
        mm += 1
        if mm <= 3:
            print(f"Idle vec {i}: MISMATCH out={out} done={done} exp={exp}")

# Frame 2: reset at 5210, warmup 3, tx_start=1 at 5210, data=255
tx.reset()
tx.step(1, 1, 1, 255)  # warmup -3 (vec 5210)
tx.step(1, 1, 0, 0)    # warmup -2 (vec 5211)
tx.step(1, 1, 0, 0)    # warmup -1 (vec 5212)

mm2 = 0
for i in range(5213, 9550):
    exp = data['vectors'][i]['expected']
    out, done = tx.step(1, 1, 0, 0)
    if out != exp.get('tx_out', 1) or done != exp.get('tx_done', 0):
        mm2 += 1
        if mm2 <= 3:
            print(f"Frame2 vec {i}: MISMATCH out={out} done={done} exp={exp}")
print(f"Frame 2 [5213..9549]: {mm2} mismatches")