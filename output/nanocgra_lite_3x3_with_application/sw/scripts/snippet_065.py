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

# CORRECT approach: lb0 = row N-1, lb1 = row N-2
# At row 2: lb0 = row 1, lb1 = row 0
# Transfer: lb1 gets lb0_data (row N-1 value), lb0 gets current px (row N)
# Window: row N-2 = lb1, row N-1 = lb0, row N = current

lb0 = LineBuffer(IMG_W)  # will hold row N-1
lb1 = LineBuffer(IMG_W)  # will hold row N-2
win = Window3x3()
results = []

for idx, px in enumerate(flat):
    row = idx // IMG_W
    col = idx % IMG_W
    # tap: lb1 = row N-2, lb0 = row N-1
    lb1_data = lb1.tap(col) if row >= 2 else 0  # row N-2
    lb0_data = lb0.tap(col) if row >= 1 else 0  # row N-1
    # window: row N-2 = lb1_data, row N-1 = lb0_data, row N = px
    w, valid = win.step(1, 1, 1, px, lb1_data, lb0_data, col, row)
    # transfer: lb1 gets lb0's value (row N-1 -> becomes row N-2), lb0 gets px (row N -> becomes row N-1)
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
print("len:", len(results), len(ref))