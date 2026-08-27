# The golden output[0] = 0x44 but my manual computation gives 0x1e for window at (2,2).
# Let me re-examine the golden sobel_stream. It uses a streaming line buffer approach.
# The golden output[0] = 0x44. Let me trace what window the golden streaming produces for the first result.

import sys, json
sys.path.insert(0, 'golden')
from model.top import sobel_stream
from model.sobel_core import sobel_compute
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
pixels = [p for row in grid['pixels'] for p in row]

# Replicate the streaming logic from top.py sobel_stream to trace windows
IMG_W = 32
lb_rn2 = [0] * IMG_W
lb_rn1 = [0] * IMG_W
wcols = [[0, 0, 0] for _ in range(3)]
results = []
windows = []
for idx, pxx in enumerate(pixels):
    row = idx // IMG_W
    col = idx % IMG_W
    pxx = int(pxx) & 0xFF
    rn2 = lb_rn2[col] if row >= 2 else 0
    rn1 = lb_rn1[col] if row >= 1 else 0
    for r in range(3):
        wcols[r] = wcols[r][1:] + [0]
    wcols[0][2] = rn2
    wcols[1][2] = rn1
    wcols[2][2] = pxx
    if row >= 1:
        lb_rn2[col] = lb_rn1[col]
    lb_rn1[col] = pxx
    if col >= 2 and row >= 2:
        w = [wcols[r][c] for r in range(3) for c in range(3)]
        gx, gy, out = sobel_compute(w)
        results.append(out)
        windows.append((row, col, w, out))

print("First 6 streaming windows:")
for i in range(6):
    r, c, w, out = windows[i]
    print(f"  result[{i}] row={r} col={c} win={w} out={hex(out)}")

print("golden results first 6:", [hex(x) for x in results[:6]])