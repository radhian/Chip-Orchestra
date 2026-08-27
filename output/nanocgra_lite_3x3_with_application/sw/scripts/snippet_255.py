import sys, json
sys.path.insert(0, 'golden')
from model.sobel_core import sobel_compute
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
px = grid['pixels']
pixels = [p for row in px for p in row]

IMG_W = 32
lb_rn2 = [0] * IMG_W
lb_rn1 = [0] * IMG_W
wcols = [[0, 0, 0] for _ in range(3)]
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
        windows.append(w)

# chip outputs
with open('waves/chip_output.mem') as f:
    clines = f.readlines()
cvals = [int(l.strip(),16) for l in clines if l.strip() and not l.startswith('//')]

# golden outputs
with open('waves/golden_output.mem') as f:
    glines = f.readlines()
gvals = [int(l.strip(),16) for l in glines if l.strip() and not l.startswith('//')]

# For each odd index, check if chip value matches golden at some other index
print("Odd index analysis (first 10):")
for i in range(1, 20, 2):
    cv = cvals[i]
    gv = gvals[i]
    # search for cv in golden
    matches = [j for j in range(len(gvals)) if gvals[j] == cv]
    print(f"  i={i} chip={hex(cv)} golden={hex(gv)} golden_matches_at={matches[:5]}")