import json, sys
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
pixels = [p for row in g['pixels'] for p in row]
IMG_W = 32

print("pixels[64..67]:", pixels[64:68])  # row 2, cols 0-3

# Let me re-trace the golden streaming model very carefully
lb_rn2 = [0]*IMG_W
lb_rn1 = [0]*IMG_W
wcols = [[0,0,0] for _ in range(3)]

def sobel_compute(win):
    w = [int(x) & 0xFF for x in win]
    gx = (-w[0] + w[2] - 2*w[3] + 2*w[5] - w[6] + w[8])
    gy = (-w[0] - 2*w[1] - w[2] + w[6] + 2*w[7] + w[8])
    mag = abs(gx) + abs(gy)
    out = max(0, min(255, mag))
    return gx, gy, out

# Trace idx 64 to 70
for idx in range(64, 70):
    row = idx // IMG_W
    col = idx % IMG_W
    px = pixels[idx]
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
        print(f"idx={idx} row={row} col={col} px={px} rn2={rn2} rn1={rn1}")
        print(f"  wcols: {wcols}")
        print(f"  win={w} out={hex(o)}")
    else:
        print(f"idx={idx} row={row} col={col} px={px} rn2={rn2} rn1={rn1} (no output)")
        print(f"  wcols: {wcols}")