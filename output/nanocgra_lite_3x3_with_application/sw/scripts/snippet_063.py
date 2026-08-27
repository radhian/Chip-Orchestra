import json, os, sys
sys.path.insert(0, 'golden')
from model.line_buffer import LineBuffer
from model.params import IMG_W

path = os.path.join('context', 'chip_input_grid.json')
with open(path) as f:
    data = json.load(f)
pixels_2d = data['pixels']
flat = [p for row in pixels_2d for p in row]

# Correct streaming: lb0 = row N-2, lb1 = row N-1
# At row 2, col 2: lb0 should hold row 0, lb1 should hold row 1
# lb0.tap(2) should = pixels_2d[0][2] = 155
# lb1.tap(2) should = pixels_2d[1][2] = 167
# current px = pixels_2d[2][2] = 169
# So window = [155, 167, 169, ...] NO wait, window is 3x3
# window[0..2] = row N-2 cols 0,1,2 = [151, 155, 155]
# window[3..5] = row N-1 cols 0,1,2 = [165, 167, 167]
# window[6..8] = row N cols 0,1,2   = [167, 169, 169]
print("Expected window at (2,2):")
print("row0:", pixels_2d[0][0:3])
print("row1:", pixels_2d[1][0:3])
print("row2:", pixels_2d[2][0:3])

# Now let's trace the CORRECT approach: tap BEFORE shift, and lb0/lb1 hold rows N-2/N-1
lb0 = LineBuffer(IMG_W)
lb1 = LineBuffer(IMG_W)

for idx, px in enumerate(flat[:3*IMG_W]):
    row = idx // IMG_W
    col = idx % IMG_W
    # tap BEFORE shift
    lb0_data = lb0.tap(col) if row >= 2 else 0
    lb1_data = lb1.tap(col) if row >= 1 else 0
    # shift: lb1 gets lb0's oldest, lb0 gets current px
    # BUT the issue is lb0.row[-1] is the OLDEST, not the right value to push to lb1
    # Actually for a shift register, we push the new value in, old falls off
    # The transfer should be: lb1 gets the value that's falling out of lb0
    # But lb0.row[-1] is the NEWEST (rightmost), not the one falling off (leftmost)
    # Wait, let me re-read: row = [oldest, ..., newest], shift left = row[1:] + [new]
    # So row[0] falls off, row[-1] is newest
    # lb1.step pushes lb0.row[-1] (newest of lb0) -- that's WRONG
    # It should push the value falling off lb0, which is lb0.row[0] BEFORE shift
    # Actually no. Let me think about what value transfers.
    
    # Actually the correct transfer: when a new pixel comes in for row N,
    # lb0 currently holds row N-2 (fully, if we're past row 2)
    # We want lb1 to become row N-1. 
    # The value that should go to lb1 is the pixel from row N-1 at this column.
    # But lb0 holds row N-2, not row N-1. So lb0.row[-1] is wrong.
    
    # The CORRECT design: lb1 should get the OLD value of lb0 at this column (before lb0 shifts)
    # i.e., lb1 gets lb0_data (the tapped value), and lb0 gets the new pixel
    # OR: lb1 gets lb0.row[col] before lb0 shifts
    
    # Let me check: at row 1, lb0 holds row 0. We want lb1 to get row 0 values.
    # So lb1 should get lb0's current value (before lb0 shifts in row 1's pixel)
    pass

# Let me try the correct approach
lb0 = LineBuffer(IMG_W)
lb1 = LineBuffer(IMG_W)
from model.window_3x3 import Window3x3
win = Window3x3()
from model.sobel_core import sobel_compute

results = []
for idx, px in enumerate(flat):
    row = idx // IMG_W
    col = idx % IMG_W
    lb0_data = lb0.tap(col) if row >= 2 else 0
    lb1_data = lb1.tap(col) if row >= 1 else 0
    w, valid = win.step(1, 1, 1, px, lb0_data, lb1_data, col, row)
    # CORRECT: lb1 gets lb0_data (the value lb0 had at this col before shift), lb0 gets px
    lb1.step(1, 1, 1, lb0_data if row >= 1 else 0)
    lb0.step(1, 1, 1, px)
    if valid:
        gx, gy, out = sobel_compute(w)
        results.append(out)

# Reference
ref = []
for y in range(30):
    for x in range(30):
        w = [pixels_2d[y + r][x + c] for r in range(3) for c in range(3)]
        _, _, o = sobel_compute(w)
        ref.append(o)

print("results[0:6]:", results[0:6])
print("ref[0:6]:", ref[0:6])
print("match:", results == ref)