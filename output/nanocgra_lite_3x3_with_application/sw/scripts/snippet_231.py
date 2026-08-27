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

# chip out[1] = 0x9c = 156. Let me brute force search for which 3x3 window gives 156.
# Search all possible 3x3 windows in the first few rows
target = 0x9c
found = []
for r in range(5):
    for c in range(IMG_W-2):
        win = [get_pixel(r+i//3, c+i%3) for i in range(9)]
        _,_,o = sobel_compute(win)
        if o == target:
            found.append((r,c,win))
print(f"Windows giving 0x9c in rows 0-4:", found[:5])

# Also check out[3] = 0x9e = 158
target = 0x9e
found2 = []
for r in range(5):
    for c in range(IMG_W-2):
        win = [get_pixel(r+i//3, c+i%3) for i in range(9)]
        _,_,o = sobel_compute(win)
        if o == target:
            found2.append((r,c,win))
print(f"Windows giving 0x9e in rows 0-4:", found2[:5])