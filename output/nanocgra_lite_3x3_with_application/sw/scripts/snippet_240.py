import json, sys
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
pixels = [p for row in g['pixels'] for p in row]
IMG_W = 32

# Wait — the golden trace shows rn2=0 and rn1=0 at row=2! That's wrong.
# The golden model says: rn2 = lb_rn2[col] if row>=2 else 0
# At row=2, rn2 = lb_rn2[col]. But lb_rn2 was only updated when row>=1.
# Let me check: lb_rn2 is updated AFTER reading rn2.
# At row=0: lb_rn2 not updated (row<1), lb_rn1[col] = px
# At row=1: rn2 = lb_rn2[col] if row>=2 else 0 = 0 (row=1 < 2)
#           lb_rn2[col] = lb_rn1[col] (row>=1), lb_rn1[col] = px
# At row=2: rn2 = lb_rn2[col] if row>=2 else 0 = lb_rn2[col]
#           lb_rn2 was updated at row=1 to lb_rn1[col] (which was row-0 pixel)
#           So rn2 = row-0 pixel ✓
#           rn1 = lb_rn1[col] if row>=1 else 0 = lb_rn1[col] = row-1 pixel ✓

# But my trace shows rn2=0 at row=2! Let me check why.
# Oh wait — I'm tracing from idx=64. But the line buffers were initialized to 0
# and I'm starting the trace from idx=64, not from idx=0!
# The wcols and lb arrays carry state from previous iterations.
# Let me trace from the beginning.

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
        results.append(o)
        if len(results) <= 4:
            print(f"out[{len(results)-1}] idx={idx} row={row} col={col}")
            print(f"  rn2={rn2} rn1={rn1} px={px}")
            print(f"  wcols={wcols}")
            print(f"  win={w} out={hex(o)}")

print("\nFirst 12 results:", [hex(x) for x in results[:12]])