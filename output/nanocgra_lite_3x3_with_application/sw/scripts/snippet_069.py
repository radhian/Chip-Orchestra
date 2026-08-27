import json, os, sys
sys.path.insert(0, 'golden')
from model.line_buffer import LineBuffer
from model.window_3x3 import Window3x3
from model.sobel_core import sobel_compute
from model.params import IMG_W

path = os.path.join('context', 'chip_input_grid.json')
with open(path) as f:
    data = json.load(f)
pixels_2d = data['pixels']
flat = [p for row in pixels_2d for p in row]

# The problem: lb0 is being overwritten with row N pixels while we still need row N-1
# At row 2, lb0 should hold row 1, but it's getting row 2 pixels pushed in.
# The transfer logic is wrong: lb0 should NOT get px during row 2 if we still need row 1 from it.
# 
# The CORRECT streaming architecture:
# - lb0 holds row N-1, lb1 holds row N-2
# - When a new pixel (row N) arrives:
#   1. Tap lb0 and lb1 at current col (get row N-1 and N-2 values)
#   2. Feed window with lb1_data (row N-2), lb0_data (row N-1), px (row N)
#   3. Transfer: lb1 gets lb0_data (row N-1 becomes N-2), lb0 gets px (row N becomes N-1)
#
# But the issue is that lb0 and lb1 are shift registers indexed by column position.
# When we push px into lb0 at col 0, it goes to position 31 (rightmost).
# At col 3, lb0.tap(3) should return row 1's pixel at col 3.
# But lb0 has already been shifted 3 times with row 2's pixels at cols 0,1,2.
# Those shifts pushed row 2 pixels into the right side, and the row 1 data shifted left.
# So lb0.tap(3) now points to a position that was row 1's col 0 (shifted left by 3) = wrong!
#
# The fundamental issue: a shift register can't be tapped by absolute column index
# while simultaneously being shifted. The tap index changes meaning as you shift.
#
# CORRECT FIX: Don't shift lb0/lb1 during the row where their data is being consumed.
# OR: use the window's column registers to hold the 3 columns, and only tap lb0/lb1
# at the current column BEFORE any shift.
#
# Actually the real issue is simpler: lb0 is a shift register. At row 2, we're shifting
# row 2 pixels into lb0 while trying to read row 1 values from it. The row 1 values
# are being destroyed by the shifts.
#
# The fix: lb0 should hold row N-1 and NOT be shifted during row N.
# Instead, lb0 should be loaded with row N only AFTER row N is complete (or use a different approach).
#
# Actually, the standard streaming approach is:
# - Line buffers are NOT shift registers tapped by column. They're RAM addressed by column.
# - OR: the window assembler shifts columns, and line buffers are written at col address.
#
# But the simplest fix for the functional model: use 2D arrays (lists) for line buffers
# that are addressed by column, not shift registers.

# Let me rewrite sobel_stream with addressed line buffers
def sobel_stream_fixed(pixels):
    assert len(pixels) == IMG_W * 32  # IMG_H
    # Use simple 2D arrays for line buffers (addressed by column)
    lb = [[0]*IMG_W for _ in range(2)]  # lb[0]=row N-2, lb[1]=row N-1
    # Window column registers: 3 rows x 3 cols
    wcols = [[0,0,0] for _ in range(3)]
    results = []
    for idx, px in enumerate(pixels):
        row = idx // IMG_W
        col = idx % IMG_W
        # Get row N-2 and N-1 values at current col
        rn2 = lb[0][col] if row >= 2 else 0
        rn1 = lb[1][col] if row >= 1 else 0
        # Shift window columns left, push new column
        for r in range(3):
            wcols[r] = wcols[r][1:] + [0]
        wcols[0][2] = rn2  # row N-2
        wcols[1][2] = rn1  # row N-1
        wcols[2][2] = px   # row N
        # Update line buffers: lb[0] gets lb[1]'s value, lb[1] gets current px
        if row >= 1:
            lb[0][col] = lb[1][col]  # row N-1 becomes row N-2
        lb[1][col] = px  # current row becomes row N-1
        # Check valid
        if col >= 2 and row >= 2:
            w = [wcols[r][c] for r in range(3) for c in range(3)]
            gx, gy, out = sobel_compute(w)
            results.append(out)
    return results

flat = [p for row in pixels_2d for p in row]
out = sobel_stream_fixed(flat)

# Reference
ref = []
for y in range(30):
    for x in range(30):
        w = [pixels_2d[y + r][x + c] for r in range(3) for c in range(3)]
        _, _, o = sobel_compute(w)
        ref.append(o)

print("out[0:6]:", out[0:6])
print("ref[0:6]:", ref[0:6])
print("match:", out == ref)
print("len:", len(out), len(ref))