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

# golden sobel_stream first 12
import sys
sys.path.insert(0, 'golden')
from model.top import sobel_stream
out = sobel_stream(pixels)
print("golden stream first 12:", [hex(x) for x in out[:12]])

# Now let's see what window the golden stream uses for out[0]
# It's the streaming model. Let me trace it.
from model.top import sobel_stream
# Let me manually trace the streaming model for the first few
lb_rn2 = [0]*IMG_W
lb_rn1 = [0]*IMG_W
wcols = [[0,0,0] for _ in range(3)]
results = []
for idx, px in enumerate(pixels):
    row = idx // IMG_W
    col = idx % IMG_W
    rn2 = lb_rn2[col] if row>=2 else 0
    rn1 = lb_rn1[col] if row>=1 else 0
    for r in range(3):
        wcols[r] = wcols[r][1:] + [0]
    wcols[0][2] = rn2
    wcols[1][2] = rn1
    wcols[2][2] = px
    if row>=1:
        lb_rn2[col] = lb_rn1[col]
    lb_rn1[col] = px
    if col>=2 and row>=2:
        w = [wcols[r][c] for r in range(3) for c in range(3)]
        gx,gy,o = sobel_compute(w)
        results.append((idx, row, col, w, o))
        if len(results) <= 12:
            print(f"out[{len(results)-1}] idx={idx} center=({row},{col}) win={w} out={hex(o)}")