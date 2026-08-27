# The chip odd values (0x9c, 0x9e, 0x9d, 0x9f) are all ~0x9e = 158.
# These are close to the pixel values in the first rows (~155-170).
# This suggests the chip is OUTPUTTING PIXEL VALUES instead of sobel results
# for odd indices. Or the window is wrong (all zeros or wrong data).
#
# Let me check: what sobel result would you get from a window of all-same values?
# If all 9 pixels are the same value v, Gx=0, Gy=0, out=0.
# If the window has some specific pattern...
#
# 0x9c = 156, 0x9e = 158, 0x9d = 157, 0x9f = 159
# These look like they could be pixel values from the image!
# Row 0: 151, 155, 155, 155, 155, ...
# Row 1: 165, 167, 167, 167, ...
# Row 2: 167, 169, 169, 169, ...
#
# 0x9c=156, 0x9e=158, 0x9d=157, 0x9f=159 — these are NOT exact pixel values
# but they're in the range. Could they be sobel of a wrong window?
#
# Let me check what sobel result you get from a 1-row window (rows N-1, N only,
# with row N-2 = 0). This would happen if the line buffer for rn2 is not
# properly loaded.

# Simulate: what if lb_rn2 (row N-2) is always 0?
import sys, json
sys.path.insert(0, 'golden')
from model.sobel_core import sobel_compute
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
px = grid['pixels']
pixels = [p for row in px for p in row]

IMG_W = 32
lb_rn1 = [0] * IMG_W
wcols = [[0, 0, 0] for _ in range(3)]
results_rn2_zero = []
for idx, pxx in enumerate(pixels):
    row = idx // IMG_W
    col = idx % IMG_W
    pxx = int(pxx) & 0xFF
    rn2 = 0  # ALWAYS ZERO - bug simulation
    rn1 = lb_rn1[col] if row >= 1 else 0
    for r in range(3):
        wcols[r] = wcols[r][1:] + [0]
    wcols[0][2] = rn2
    wcols[1][2] = rn1
    wcols[2][2] = pxx
    lb_rn1[col] = pxx
    if col >= 2 and row >= 2:
        w = [wcols[r][c] for r in range(3) for c in range(3)]
        out = sobel_compute(w)[2]
        results_rn2_zero.append(out)

with open('waves/chip_output.mem') as f:
    clines = f.readlines()
cvals = [int(l.strip(),16) for l in clines if l.strip() and not l.startswith('//')]

print("With rn2 always 0:")
print("first 20:", [hex(x) for x in results_rn2_zero[:20]])
print("chip    :", [hex(x) for x in cvals[:20]])
print("match even:", all(results_rn2_zero[i]==cvals[i] for i in range(0,20,2)))
print("match odd:", all(results_rn2_zero[i]==cvals[i] for i in range(1,20,2)))