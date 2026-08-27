import json
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# Only the last vec has rst_n=0. So no reset between frames.
# The baud_gen runs continuously. But frame 2 starts at 5643 which is not a tick.
# 
# Let me reconsider the timing model. Maybe the vectors were generated with
# the RTL simulation where baud_tick is REGISTERED. In the RTL:
# - baud_tick is a reg, set on posedge clk
# - uart_tx checks baud_tick on posedge clk
# So there's a 1-cycle pipeline: baud_gen sets tick on cycle N, uart_tx sees it on cycle N+1.
# 
# In the golden model, both happen in the same step() call (combinational).
# 
# Let me model the RTL's 1-cycle delay:
# baud_gen: tick=1 at cycle 433 (registered, visible from cycle 433)
# uart_tx: sees tick=1 at cycle 434 (next posedge)
# So frame 1 would start at cycle 434, not 430 or 433.
# 
# But the vector shows frame 1 at 430. That's even earlier. Doesn't help.
#
# Let me try yet another approach. Maybe the vector generation script applied
# tx_start=1 for multiple cycles, not just one. Let me check if tx_start=1
# for the first 3 cycles (warmup) would shift the timing.
#
# With tx_start=1 for 3 warmup cycles and the golden model:
# warmup -3: tx_start=1, start_req=1
# warmup -2: tx_start=1, start_req=1 (already set)
# warmup -1: tx_start=1, start_req=1
# vec 0: tx_start=0, baud_gen cnt=3
# ...
# vec 430: cnt=433, tick=1, IDLE sees start_req, START, tx_out=0
# This gives frame 1 at 430. Correct.
#
# For frame 2: if tx_start=1 at vec 5640, 5641, 5642 (3 cycles):
# start_req latched at 5640. Next tick after 5640...
# Ticks at 430+434*k. 430+12*434=5638 (before 5640). 430+13*434=6072 (after 5640).
# So frame 2 would start at 6072. Not 5643.
#
# I think the vector file might have been generated with a reset of the baud_gen
# between frames, even though rst_n=1 in the vectors. Maybe the generation script
# created a fresh UartTx instance for each frame.
#
# Let me test this hypothesis: fresh UartTx for each frame with 3-warmup.
frame_info = [
    (60, 430, 4336),
    (255, 5643, 9549),
    (165, 10856, 14762),
    (0, 16069, 19975),
]

all_match = True
pos = 0  # global vector position
for frame_idx, (data_byte, start_vec, end_vec) in enumerate(frame_info):
    tx = UartTx()
    tx.reset()
    # 3 warmup cycles
    tx.step(1, 1, 1, data_byte)
    tx.step(1, 1, 0, 0)
    tx.step(1, 1, 0, 0)
    
    # The frame occupies vecs [start_vec .. end_vec]
    # Before start_vec, the model should be idle (tx_out=1)
    # We need to check: for vecs from previous frame end+1 to start_vec-1,
    # the model outputs tx_out=1 (idle)
    
    # Actually, with a fresh model, the warmup produces tx_out=1 (idle) for
    # the first 430 cycles. Then frame starts at 430.
    # But the vector file has the frame starting at start_vec, which may not be 430
    # relative to the fresh model.
    
    # For frame 0: fresh model, warmup, frame at 430. Vectors 0..4336.
    # For frame 1: we need frame at 5643. But fresh model gives frame at 430.
    # So we'd need to run 5643-430=5213 idle cycles before the frame.
    # That means: fresh model, warmup, run 5213 cycles (all idle), then frame at 5643.
    # But the warmup already starts the frame at 430. So we can't have idle cycles
    # before the frame with a fresh model + warmup.
    
    # UNLESS: fresh model, NO warmup, tx_start=1 at vec (start_vec-3).
    # Then first tick at start_vec-3+433=start_vec+430. That's too late.
    
    # OR: fresh model, tx_start=1 at vec (start_vec-430).
    # First tick at start_vec-430+433=start_vec+3. Close but off by 3.
    
    # OR: fresh model with 3 warmup BEFORE the frame:
    # reset at start_vec-430-3, warmup 3, first tick at start_vec.
    # But we need to fill vecs 0..start_vec-1 with idle (tx_out=1).
    
    # This is getting too complicated. Let me just check if a fresh model per frame
    # with 3 warmup matches the frame's vectors.
    
    start = start_vec
    end = end_vec
    mismatches = 0
    for i in range(start, end+1):
        exp = data['vectors'][i]['expected']
        out, done = tx.step(1, 1, 0, 0)
        if out != exp.get('tx_out', 1) or done != exp.get('tx_done', 0):
            mismatches += 1
            if mismatches <= 3:
                print(f"Frame {frame_idx} vec {i}: MISMATCH out={out} done={done} exp={exp}")
    print(f"Frame {frame_idx} [{start}..{end}]: {mismatches} mismatches")
    if mismatches > 0:
        all_match = False

print(f"\nAll frames match: {all_match}")