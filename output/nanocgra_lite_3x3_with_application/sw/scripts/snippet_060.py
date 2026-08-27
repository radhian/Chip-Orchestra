import json, os, sys
sys.path.insert(0, 'golden')
from model.sobel_core import sobel_compute
from model.params import IMG_W, IMG_H, OUT_W, OUT_H

path = os.path.join('context', 'chip_input_grid.json')
with open(path) as f:
    data = json.load(f)
pixels_2d = data['pixels']

# Reference: direct 2D sobel for output (0,0) -> window rows 0,1,2 cols 0,1,2
w = [pixels_2d[r][c] for r in range(3) for c in range(3)]
gx, gy, out = sobel_compute(w)
print("ref window (0,0):", w)
print("ref gx,gy,out:", gx, gy, out)

# Now simulate the streaming model manually to see what window it produces for the first valid output
# Replicate sobel_stream logic
from model.line_buffer import LineBuffer
from model.window_3x3 import Window3x3

flat = [p for row in pixels_2d for p in row]
lb0 = LineBuffer(IMG_W)
lb1 = LineBuffer(IMG_W)
win = Window3x3()
results = []
first_valid_info = None
for idx, px in enumerate(flat):
    row = idx // IMG_W
    col = idx % IMG_W
    lb0_data = lb0.tap(col) if row >= 2 else 0
    lb1_data = lb1.tap(col) if row >= 1 else 0
    w2, valid = win.step(1, 1, 1, px, lb0_data, lb1_data, col, row)
    lb1.step(1, 1, 1, lb0.row[-1] if row >= 1 else 0)
    lb0.step(1, 1, 1, px)
    if valid:
        gx2, gy2, out2 = sobel_compute(w2)
        if first_valid_info is None:
            first_valid_info = (idx, row, col, list(w2), out2)
        results.append(out2)

print("first valid:", first_valid_info)
print("streaming out[0]:", results[0])
print("ref out[0]:", out)