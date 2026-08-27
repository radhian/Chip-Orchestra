import json
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
pixels = [p for row in g['pixels'] for p in row]

# Manually compute sobel for the first few windows to understand the golden
def sobel_compute(win):
    w = [int(x) & 0xFF for x in win]
    gx = (-w[0] + w[2] - 2*w[3] + 2*w[5] - w[6] + w[8])
    gy = (-w[0] - 2*w[1] - w[2] + w[6] + 2*w[7] + w[8])
    mag = abs(gx) + abs(gy)
    out = max(0, min(255, mag))
    return gx, gy, out

# The first output is at row=2, col=2 (index 0 of output)
# window centered at (2,2): rows 1,2,3 cols 1,2,3
IMG_W = 32
def get_pixel(r, c):
    return pixels[r*IMG_W + c]

# First output window: centered at (2,2)
for out_idx in range(12):
    r = 2 + out_idx // 30
    c = 2 + out_idx % 30
    win = [get_pixel(r-1+i//3, c-1+i%3) for i in range(9)]
    gx, gy, out = sobel_compute(win)
    print(f"out[{out_idx}] center=({r},{c}) win={win} gx={gx} gy={gy} out={hex(out)}")