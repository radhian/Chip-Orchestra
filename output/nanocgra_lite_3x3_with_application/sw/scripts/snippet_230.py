import re
def load_mem(path):
    vals = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            for tok in line.split():
                if tok.startswith('//'): break
                vals.append(int(tok, 16))
    return vals

chip = load_mem('waves/chip_output.mem')
golden = load_mem('waves/golden_output.mem')

# Pattern: odd indices mismatch, even indices match (for the first ~24)
# Let's check more broadly
mismatch_parity = [0,0]  # even, odd
for i in range(900):
    if chip[i] != golden[i]:
        mismatch_parity[i%2] += 1
print("mismatches even idx:", mismatch_parity[0], "odd idx:", mismatch_parity[1])

# So odd indices (col 1,3,5...) mismatch. Even indices (col 0,2,4...) match.
# This is a column-parity issue in the window assembler!
# The window is wrong on odd columns.

# Let's check: for odd output columns, what's the chip value vs golden?
# out[1] = col 1 (odd). golden=0x38, chip=0x9c
# out[3] = col 3 (odd). golden=0x3c, chip=0x9e

# Let me compute what window would give chip's values.
# For out[1] (row 0, col 1 in output grid), golden window = rows 0,1,2 cols 1,2,3
import json
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
pixels = [p for row in g['pixels'] for p in row]
IMG_W = 32
def get_pixel(r, c):
    return pixels[r*IMG_W + c]

def sobel_compute(win):
    w = [int(x) & 0xFF for x in win]
    gx = (-w[0] + w[2] - 2*w[3] + 2*w[5] - w[6] + w[8])
    gy = (-w[0] - 2*w[1] - w[2] + w[6] + 2*w[7] + w[8])
    mag = abs(gx) + abs(gy)
    out = max(0, min(255, mag))
    return gx, gy, out

# golden out[1] window: rows 0,1,2 cols 1,2,3
win_g = [get_pixel(0,1),get_pixel(0,2),get_pixel(0,3), get_pixel(1,1),get_pixel(1,2),get_pixel(1,3), get_pixel(2,1),get_pixel(2,2),get_pixel(2,3)]
print("golden out[1] win:", win_g, "->", hex(sobel_compute(win_g)[2]))

# chip out[1] = 0x9c = 156. What window gives 156?
# Let me try: maybe the chip shifts wrong on odd cols, using col 2,3,4 instead of 1,2,3?
win_c = [get_pixel(0,2),get_pixel(0,3),get_pixel(0,4), get_pixel(1,2),get_pixel(1,3),get_pixel(1,4), get_pixel(2,2),get_pixel(2,3),get_pixel(2,4)]
print("chip candidate (cols 2,3,4):", win_c, "->", hex(sobel_compute(win_c)[2]))

# Or maybe cols 0,1,2 (same as out[0])?
win_c0 = [get_pixel(0,0),get_pixel(0,1),get_pixel(0,2), get_pixel(1,0),get_pixel(1,1),get_pixel(1,2), get_pixel(2,0),get_pixel(2,1),get_pixel(2,2)]
print("chip candidate (cols 0,1,2):", win_c0, "->", hex(sobel_compute(win_c0)[2]))

# Or maybe the chip is using a STALE window from the previous column?
# out[0] window = cols 0,1,2. If out[1] reuses out[0]'s window... that's 0x44 not 0x9c.
# Let me try cols 1,2,3 but with wrong row (rows 1,2,3)?
win_r = [get_pixel(1,1),get_pixel(1,2),get_pixel(1,3), get_pixel(2,1),get_pixel(2,2),get_pixel(2,3), get_pixel(3,1),get_pixel(3,2),get_pixel(3,3)]
print("chip candidate (rows 1,2,3 cols 1,2,3):", win_r, "->", hex(sobel_compute(win_r)[2]))